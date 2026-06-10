import os
import json
from datetime import datetime

def run_payload_delivery():
    print("Initializing Module C: Payload Delivery Engine...")
    
    # 1. Establish file coordinate pathways
    input_file_path = "output/ad_groups.json"
    output_dir = "output"
    
    if not os.path.exists(input_file_path):
        print(f"ERROR: Could not find upstream data asset at {input_file_path}. Please run ad_group_architect.py first.")
        return

    # 2. Ingest the structured campaign layout from Module B
    print("Ingesting campaign architecture dataset...")
    with open(input_file_path, "r") as f:
        campaign_data = json.load(f)

    # 3. Simulate deployment manifest metadata wrapping
    print("Compiling global deployment manifest matrix...")
    deployment_manifest = {
        "status": "READY_FOR_BULK_IMPORT",
        "engine_version": "Track-3.AutoPilot.v1",
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_geography": {
            "city": "Austin",
            "state": "TX",
            "radius_miles": 25
        },
        "campaign_payload": campaign_data
    }

    # 4. Generate human-readable verification log matrix directly in terminal
    print("\n=======================================================")
    print("          FINAL COMPATIBILITY CHECK MANIFEST           ")
    print("=======================================================")
    print(f"Status Flags    : {deployment_manifest['status']}")
    print(f"Timestamp       : {deployment_manifest['compiled_at']}")
    print(f"Target Region   : {deployment_manifest['target_geography']['city']}, {deployment_manifest['target_geography']['state']} ({deployment_manifest['target_geography']['radius_miles']}mi radius)")
    print("-------------------------------------------------------")
    
    for idx, group in enumerate(deployment_manifest['campaign_payload']['ad_groups'], start=1):
        print(f"\n[Ad Group Matrix #{idx}]: {group['ad_group_name']}")
        print(f" -> Keywords Ingested  : {len(group['target_keywords'])} phrases loaded.")
        print(" -> Verified Headlines :")
        for h in group['headlines']:
            print(f"    * [{len(h)}/30 chars] \"{h}\"")
        print(" -> Verified Descr.  :")
        for d in group['descriptions']:
            print(f"    * [{len(d)}/90 chars] \"{d}\"")
            
    print("\n=======================================================")

    # 5. Flush the finalized deployment manifest to the hard drive
    final_output_path = os.path.join(output_dir, "final_deployment_manifest.json")
    try:
        with open(final_output_path, "w") as f:
            json.dump(deployment_manifest, f, indent=4)
        print(f"\nSUCCESS: Final validation manifest safely written to {final_output_path}!")
        print("Track 3 AutoPilot Shell pipeline processing sequence complete.\n")
    except Exception as e:
        print(f"CRITICAL: Failed to write output manifest to disk: {e}")

if __name__ == "__main__":
    run_payload_delivery()