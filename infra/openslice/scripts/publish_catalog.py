#!/usr/bin/env python3
"""Publication idempotente du catalogue CFS/RFS sur OpenSlice (TMF633) + marketplace.

Ordre d'execution :
  1. ResourceSpecifications logiques (transport-slice NSC, chart Helm CRIDGE) ;
     verification de la presence des ResourceSpecs issues des NSD OSM (synchronisees
     par l'adaptateur OSM d'OpenSlice : ran_xr_edge_ns, edge_mec_ns, core_5g_ns).
  2. RFS (ResourceFacingServiceSpecification) -> referencent les ResourceSpecs.
  3. CFS atomiques -> reliees aux RFS (relationshipType=isRealizedBy).
  4. CFS composites (isBundle) -> bundles/requires vers les CFS atomiques.
  5. Catalogue + categorie, rattachement des CFS, lifecycleStatus=Active (marketplace).

Usage : python3 publish_catalog.py --env env.json [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

HERE = Path(__file__).resolve().parent
RS_DIR = HERE.parent / "resource-specs"
RFS_DIR = HERE.parent / "rfs"
CFS_DIR = HERE.parent / "cfs"

SC = "/serviceCatalogManagement/v4"
RC = "/resourceCatalogManagement/v4"

# Les composites referencant les atomiques, l'ordre de creation compte.
CFS_ORDER = [
    "CFS_eMBB_XR_Edge.json",
    "CFS_URLLC_Actuation.json",
    "CFS_Transport_InterSite.json",
    "CFS_Edge_Hosting.json",
    "CFS_FieldAssist_Base.json",
    "CFS_FieldAssist_WithActuation.json",
]

# ResourceSpecs attendues cote adaptateur OSM (NSD synchronises)
OSM_SYNCED_RS = ["ran_xr_edge_ns", "edge_mec_ns", "core_5g_ns"]


class OpenSlice:
    def __init__(self, cfg, dry_run=False):
        self.cfg = cfg
        self.dry = dry_run
        self.s = requests.Session()
        self.s.verify = cfg.get("verify_tls", True)
        if not self.dry:
            self._login()

    def _login(self):
        r = self.s.post(
            self.cfg["oauth_token_url"],
            data={
                "grant_type": "password",
                "client_id": self.cfg["oauth_client_id"],
                "username": self.cfg["username"],
                "password": self.cfg["password"],
            },
            timeout=30,
        )
        r.raise_for_status()
        self.s.headers["Authorization"] = "Bearer " + r.json()["access_token"]

    def _url(self, path):
        return self.cfg["api_base"].rstrip("/") + path

    def get_by_name(self, path, name):
        if self.dry:
            return None
        r = self.s.get(self._url(path), params={"name": name}, timeout=30)
        r.raise_for_status()
        items = [i for i in r.json() if i.get("name") == name]
        return items[0] if items else None

    def upsert(self, path, payload):
        name = payload["name"]
        existing = self.get_by_name(path, name)
        if self.dry:
            print(f"[dry-run] upsert {path} <- {name}")
            return {"id": f"dry-{name}", "name": name}
        if existing:
            r = self.s.patch(self._url(f"{path}/{existing['id']}"), json=payload, timeout=30)
            r.raise_for_status()
            print(f"  = mis a jour : {name} ({existing['id']})")
            return r.json()
        r = self.s.post(self._url(path), json=payload, timeout=30)
        r.raise_for_status()
        created = r.json()
        print(f"  + cree : {name} ({created.get('id')})")
        return created


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def spec_ref(spec, rel_type):
    return {
        "id": spec["id"],
        "name": spec["name"],
        "relationshipType": rel_type,
        "@referredType": "ServiceSpecification",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = load(args.env)
    os_api = OpenSlice(cfg, dry_run=args.dry_run)

    print("=== 1/5 ResourceSpecifications ===")
    rs_ids = {}
    for f in sorted(RS_DIR.glob("*.json")):
        payload = load(f)
        created = os_api.upsert(f"{RC}/resourceSpecification", payload)
        rs_ids[payload["name"]] = created
    for name in OSM_SYNCED_RS:
        found = os_api.get_by_name(f"{RC}/resourceSpecification", name)
        if found:
            rs_ids[name] = found
            print(f"  = NSD OSM synchronise : {name} ({found['id']})")
        else:
            print(f"  ! ATTENTION : ResourceSpec '{name}' absente - verifier l'adaptateur OSM "
                  f"d'OpenSlice (synchronisation des NSD) avant d'instancier la RFS associee.")

    print("=== 2/5 RFS ===")
    spec_ids = {}
    for f in sorted(RFS_DIR.glob("*.json")):
        payload = load(f)
        res_names = payload.pop("_resourceSpecs", [])
        payload.pop("_type", None)
        payload["resourceSpecification"] = [
            {"id": rs_ids[n]["id"], "name": n, "@referredType": "ResourceSpecification"}
            for n in res_names if n in rs_ids
        ]
        spec_ids[payload["name"]] = os_api.upsert(f"{SC}/serviceSpecification", payload)

    print("=== 3/5 + 4/5 CFS (atomiques puis composites) ===")
    for fname in CFS_ORDER:
        payload = load(CFS_DIR / fname)
        rels = payload.pop("_relationships", [])
        payload.pop("_type", None)
        payload["serviceSpecRelationship"] = [
            spec_ref(spec_ids[r["name"]], r["relationshipType"])
            for r in rels if r["name"] in spec_ids
        ]
        missing = [r["name"] for r in rels if r["name"] not in spec_ids]
        if missing:
            print(f"  ! {payload['name']} : relations non resolues {missing}")
        spec_ids[payload["name"]] = os_api.upsert(f"{SC}/serviceSpecification", payload)

    print("=== 5/5 Catalogue + categorie + marketplace ===")
    category = os_api.upsert(f"{SC}/serviceCategory", {
        "name": cfg["category_name"],
        "description": "Assistance metavers du technicien terrain (slicing 5G multi-domaine)",
        "lifecycleStatus": "Active",
        "serviceCandidate": [],
    })
    os_api.upsert(f"{SC}/serviceCatalog", {
        "name": cfg["catalog_name"],
        "description": "Catalogue du PoC FieldAssist : composites + CFS atomiques",
        "lifecycleStatus": "Active",
        "category": [{"id": category["id"], "name": category["name"]}],
    })
    for name in cfg["marketplace_cfs"]:
        if name not in spec_ids:
            print(f"  ! CFS inconnue : {name}")
            continue
        spec = spec_ids[name]
        if args.dry_run:
            print(f"[dry-run] activation marketplace : {name}")
            continue
        r = os_api.s.patch(
            os_api._url(f"{SC}/serviceSpecification/{spec['id']}"),
            json={"lifecycleStatus": "Active"},
            timeout=30,
        )
        r.raise_for_status()
        print(f"  * publie au marketplace : {name}")

    print("\nTermine. Verifier dans le portail OpenSlice : Service Catalogs > "
          f"'{cfg['catalog_name']}' et le Marketplace. Importer ensuite les regles LCM "
          "(infra/openslice/lcm-rules/README.md).")


if __name__ == "__main__":
    main()
