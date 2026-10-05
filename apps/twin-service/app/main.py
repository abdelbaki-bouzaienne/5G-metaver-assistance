"""twin-service : modele metier du jumeau numerique (plan 2, REST).

Le splat sert a la visualisation ; la logique metier (sites, versions immuables,
entites, ports, clients, cables, annotations) vit ici, en coordonnees du repere
jumeau (origine = marqueur image).
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/twin.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


class Site(Base):
    __tablename__ = "sites"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    site_type = Column(String, default="NRO")  # NRO / PM / PB
    address = Column(String, nullable=True)
    marker_id = Column(String, nullable=False)
    marker_size_mm = Column(Float, nullable=False, default=150)


class TwinVersion(Base):
    __tablename__ = "twin_versions"
    id = Column(String, primary_key=True, default=uid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    created_at = Column(DateTime, default=now)
    status = Column(String, default="ready")  # processing / ready / failed
    transform_marker = Column(JSON, nullable=True)  # 4x4 splat -> repere jumeau
    quality_score = Column(Float, nullable=True)
    coverage = Column(Float, nullable=True)
    review_status = Column(String, default="pending")  # pending / approved / rejected


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, default=uid)
    version_id = Column(String, ForeignKey("twin_versions.id"), nullable=False)
    asset_type = Column(String, nullable=False)  # raw / splat / tile
    lod = Column(Integer, default=0)
    uri = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    checksum = Column(String, nullable=True)


class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, default=uid)
    version_id = Column(String, ForeignKey("twin_versions.id"), nullable=False)
    entity_type = Column(String, nullable=False)  # panel_left/panel_right/central_zone/port/custom
    name = Column(String, nullable=False)
    geometry = Column(JSON, nullable=False)  # {kind: box|point, ...} repere jumeau
    meta = Column(JSON, default=dict)


class Client(Base):
    __tablename__ = "clients"
    id = Column(String, primary_key=True, default=uid)
    reference = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)


class Port(Base):
    __tablename__ = "ports"
    id = Column(String, primary_key=True, default=uid)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False)
    index = Column(Integer, nullable=False)
    label = Column(String, nullable=False)
    client_id = Column(String, ForeignKey("clients.id"), nullable=True)
    status = Column(String, default="free")  # free / used / faulty


class Cable(Base):
    __tablename__ = "cables"
    id = Column(String, primary_key=True, default=uid)
    port_left_id = Column(String, ForeignKey("ports.id"), nullable=False)
    port_right_id = Column(String, ForeignKey("ports.id"), nullable=False)
    path = Column(JSON, nullable=True)  # polyline repere jumeau (zone centrale)
    status = Column(String, default="planned")  # planned / installed / removed


class Annotation(Base):
    __tablename__ = "annotations"
    id = Column(String, primary_key=True, default=uid)
    version_id = Column(String, ForeignKey("twin_versions.id"), nullable=False)
    session_id = Column(String, nullable=True)
    author = Column(String, nullable=False)
    annotation_type = Column(String, nullable=False)  # highlight / draw / text / gesture
    geometry = Column(JSON, nullable=False)  # repere jumeau, jamais ecran
    created_at = Column(DateTime, default=now)


Base.metadata.create_all(engine)
app = FastAPI(title="twin-service", version="1.0.0")


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def must(obj, name="objet"):
    if obj is None:
        raise HTTPException(404, f"{name} introuvable")
    return obj


def dump(o) -> dict:
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


# --------------------------------------------------------------------------- sites
class SiteIn(BaseModel):
    name: str
    site_type: str = "NRO"
    address: Optional[str] = None
    marker_id: str
    marker_size_mm: float = 150


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "twin-service"}


@app.post("/sites", status_code=201)
def create_site(body: SiteIn, s: Session = Depends(db)):
    site = Site(**body.model_dump())
    s.add(site); s.commit()
    return dump(site)


@app.get("/sites/{site_id}")
def get_site(site_id: str, s: Session = Depends(db)):
    return dump(must(s.get(Site, site_id), "site"))


@app.get("/sites/{site_id}/twin-versions")
def list_versions(site_id: str, s: Session = Depends(db)):
    return [dump(v) for v in s.query(TwinVersion).filter_by(site_id=site_id).order_by(TwinVersion.created_at)]


@app.get("/sites/{site_id}/diff")
def diff_versions(site_id: str, frm: str = Query(alias="from"), to: str = Query(...), s: Session = Depends(db)):
    """Comparaison simple de deux versions : entites ajoutees / supprimees / deplacees."""
    a = {e.name: e for e in s.query(Entity).filter_by(version_id=frm)}
    b = {e.name: e for e in s.query(Entity).filter_by(version_id=to)}
    moved = [n for n in a.keys() & b.keys() if a[n].geometry != b[n].geometry]
    return {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "moved": sorted(moved)}


# ------------------------------------------------------------------- twin versions
class VersionIn(BaseModel):
    site_id: str
    transform_marker: Optional[list] = None
    quality_score: Optional[float] = None
    coverage: Optional[float] = None
    assets: list[dict] = []


@app.post("/twin-versions", status_code=201)
def create_version(body: VersionIn, s: Session = Depends(db)):
    must(s.get(Site, body.site_id), "site")
    v = TwinVersion(site_id=body.site_id, transform_marker=body.transform_marker,
                    quality_score=body.quality_score, coverage=body.coverage)
    s.add(v); s.flush()
    for a in body.assets:
        s.add(Asset(version_id=v.id, **a))
    s.commit()
    return dump(v)


@app.get("/twin-versions/{vid}")
def get_version(vid: str, s: Session = Depends(db)):
    return dump(must(s.get(TwinVersion, vid), "version"))


@app.post("/twin-versions/{vid}/review")
def review_version(vid: str, body: dict, s: Session = Depends(db)):
    """Validation humaine : un scan ne met jamais a jour le SI de lui-meme."""
    v = must(s.get(TwinVersion, vid), "version")
    v.review_status = "approved" if body.get("approved") else "rejected"
    s.commit()
    return dump(v)


@app.get("/twin-versions/{vid}/assets")
def version_assets(vid: str, lod: Optional[str] = None, s: Session = Depends(db)):
    q = s.query(Asset).filter_by(version_id=vid)
    if lod == "low":
        q = q.filter(Asset.lod >= 1)
    # En production : transformer uri en URL S3 signee courte duree (presign cote gateway)
    return [dump(a) for a in q]


# ------------------------------------------------------------ entites / ports / clients
class EntityIn(BaseModel):
    entity_type: str
    name: str
    geometry: dict
    meta: dict = {}


@app.post("/twin-versions/{vid}/entities", status_code=201)
def create_entity(vid: str, body: EntityIn, s: Session = Depends(db)):
    must(s.get(TwinVersion, vid), "version")
    e = Entity(version_id=vid, **body.model_dump())
    s.add(e); s.commit()
    return dump(e)


@app.get("/twin-versions/{vid}/entities")
def list_entities(vid: str, type: Optional[str] = None, s: Session = Depends(db)):
    q = s.query(Entity).filter_by(version_id=vid)
    if type:
        q = q.filter_by(entity_type=type)
    return [dump(e) for e in q]


class PortIn(BaseModel):
    index: int
    label: str


@app.post("/entities/{eid}/ports", status_code=201)
def create_port(eid: str, body: PortIn, s: Session = Depends(db)):
    must(s.get(Entity, eid), "entite")
    p = Port(entity_id=eid, **body.model_dump())
    s.add(p); s.commit()
    return dump(p)


@app.patch("/ports/{pid}")
def patch_port(pid: str, body: dict, s: Session = Depends(db)):
    p = must(s.get(Port, pid), "port")
    for k in ("client_id", "status", "label"):
        if k in body:
            setattr(p, k, body[k])
    if body.get("client_id"):
        p.status = "used"
    s.commit()
    return dump(p)


class ClientIn(BaseModel):
    reference: str
    name: str


@app.post("/clients", status_code=201)
def create_client(body: ClientIn, s: Session = Depends(db)):
    c = Client(**body.model_dump())
    s.add(c); s.commit()
    return dump(c)


@app.get("/clients/{cid}/ports")
def client_ports(cid: str, s: Session = Depends(db)):
    """Conformite client : le systeme resout automatiquement les positions
    (panneau gauche + droit) a surligner chez le technicien."""
    must(s.get(Client, cid), "client")
    out = []
    for p in s.query(Port).filter_by(client_id=cid):
        entity = s.get(Entity, p.entity_id)
        out.append({**dump(p), "panel": entity.entity_type, "panel_geometry": entity.geometry})
    return out


# ------------------------------------------------------------------------- cables
class CableIn(BaseModel):
    port_left_id: str
    port_right_id: str


@app.post("/cables", status_code=201)
def create_cable(body: CableIn, s: Session = Depends(db)):
    must(s.get(Port, body.port_left_id), "port gauche")
    must(s.get(Port, body.port_right_id), "port droit")
    c = Cable(**body.model_dump())
    s.add(c); s.commit()
    return dump(c)


@app.patch("/cables/{cid}")
def patch_cable(cid: str, body: dict, s: Session = Depends(db)):
    c = must(s.get(Cable, cid), "cable")
    for k in ("path", "status"):
        if k in body:
            setattr(c, k, body[k])
    s.commit()
    return dump(c)


# -------------------------------------------------------------------- annotations
class AnnotationIn(BaseModel):
    annotation_type: str
    author: str
    geometry: dict
    session_id: Optional[str] = None


@app.post("/twin-versions/{vid}/annotations", status_code=201)
def create_annotation(vid: str, body: AnnotationIn, s: Session = Depends(db)):
    must(s.get(TwinVersion, vid), "version")
    a = Annotation(version_id=vid, **body.model_dump())
    s.add(a); s.commit()
    return dump(a)


@app.get("/twin-versions/{vid}/annotations")
def list_annotations(vid: str, s: Session = Depends(db)):
    return [dump(a) for a in s.query(Annotation).filter_by(version_id=vid)]


# ------------------------------------------------------------------------- import
@app.post("/import")
def import_inventory(body: dict, s: Session = Depends(db)):
    """Import d'un referentiel existant (clients / ports / cables), reconcilie par reference."""
    created: dict[str, Any] = {"clients": 0, "ports_linked": 0}
    for c in body.get("clients", []):
        if not s.query(Client).filter_by(reference=c["reference"]).first():
            s.add(Client(reference=c["reference"], name=c.get("name", c["reference"])))
            created["clients"] += 1
    s.flush()
    for link in body.get("port_links", []):  # {port_label, client_reference}
        port = s.query(Port).filter_by(label=link["port_label"]).first()
        client = s.query(Client).filter_by(reference=link["client_reference"]).first()
        if port and client:
            port.client_id = client.id
            port.status = "used"
            created["ports_linked"] += 1
    s.commit()
    return created
