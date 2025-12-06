#!/usr/bin/env python3
"""
Provision a new drone with AWS IoT certificates.

Usage:
    python provision_drone.py <drone_id>

Example:
    python provision_drone.py drone-1
"""

import boto3
import sys
import os
import json


def provision_drone(drone_id: str, output_dir: str = "../../certs"):
    """Provision a new drone with IoT Thing and certificates"""
    
    iot = boto3.client('iot')
    
    print(f"🚁 Provisioning {drone_id}...")
    
    # 1. Create IoT Thing
    try:
        thing_response = iot.create_thing(thingName=drone_id)
        print(f"✅ Created IoT Thing: {drone_id}")
    except iot.exceptions.ResourceAlreadyExistsException:
        print(f"ℹ️  IoT Thing {drone_id} already exists")
    
    # 2. Create certificate and keys
    cert_response = iot.create_keys_and_certificate(setAsActive=True)
    cert_id = cert_response['certificateId']
    cert_arn = cert_response['certificateArn']
    
    print(f"✅ Created certificate: {cert_id[:16]}...")
    
    # 3. Create output directory
    os.makedirs(f"{output_dir}/{drone_id}", exist_ok=True)
    
    # 4. Save certificate files
    with open(f"{output_dir}/{drone_id}/certificate.pem", 'w') as f:
        f.write(cert_response['certificatePem'])
    
    with open(f"{output_dir}/{drone_id}/private.key", 'w') as f:
        f.write(cert_response['keyPair']['PrivateKey'])
    
    with open(f"{output_dir}/{drone_id}/public.key", 'w') as f:
        f.write(cert_response['keyPair']['PublicKey'])
    
    # Download Amazon Root CA if not exists
    if not os.path.exists(f"{output_dir}/AmazonRootCA1.pem"):
        import urllib.request
        url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
        urllib.request.urlretrieve(url, f"{output_dir}/AmazonRootCA1.pem")
        print("✅ Downloaded Amazon Root CA")
    
    print(f"✅ Saved certificates to {output_dir}/{drone_id}/")
    
    # 5. Attach policy to certificate
    try:
        iot.attach_policy(
            policyName='AetherDronePolicy',
            target=cert_arn
        )
        print(f"✅ Attached policy: AetherDronePolicy")
    except Exception as e:
        print(f"⚠️  Warning: Could not attach policy: {e}")
        print("   Make sure to deploy the CDK stack first!")
    
    # 6. Attach certificate to thing
    iot.attach_thing_principal(
        thingName=drone_id,
        principal=cert_arn
    )
    print(f"✅ Attached certificate to thing")
    
    # 7. Save metadata
    metadata = {
        "drone_id": drone_id,
        "certificate_id": cert_id,
        "certificate_arn": cert_arn,
        "thing_arn": f"arn:aws:iot:{iot.meta.region_name}:{boto3.client('sts').get_caller_identity()['Account']}:thing/{drone_id}"
    }
    
    with open(f"{output_dir}/{drone_id}/metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n🎉 Successfully provisioned {drone_id}!")
    print(f"\nCertificate files:")
    print(f"  - {output_dir}/{drone_id}/certificate.pem")
    print(f"  - {output_dir}/{drone_id}/private.key")
    print(f"  - {output_dir}/AmazonRootCA1.pem")
    print(f"\nMetadata: {output_dir}/{drone_id}/metadata.json")
    
    return metadata


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python provision_drone.py <drone_id>")
        print("Example: python provision_drone.py drone-1")
        sys.exit(1)
    
    drone_id = sys.argv[1]
    provision_drone(drone_id)
