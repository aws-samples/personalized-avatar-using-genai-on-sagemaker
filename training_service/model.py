from djl_python import Input, Output
from trainer import Trainer
from io import BytesIO
from pathlib import Path
import os
from utils import preprocess_images
import shutil
import tarfile
import uuid
import subprocess
import json
import boto3

is_initialized = False
s3_bucket = None
s3_prefix = None
mme_prefix = None
s3_client = boto3.client('s3')

def handle(inputs: Input):
    
    global is_initialized
    global s3_bucket
    global s3_prefix
    global mme_prefix
     
    if not is_initialized:
        properties = inputs.get_properties()
        s3_bucket = properties.get("s3_bucket")
        s3_prefix = properties.get("s3_prefix")
        mme_prefix = properties.get("mme_prefix")
        is_initialized = True

    if inputs.is_empty():
        return None
    
    
    tar_buffer = BytesIO(inputs.get_as_bytes())
    train_path, tuning_config = preprocess_images(tar_buffer)

    
    class_data_dir = Path("/tmp/priors")
    if not class_data_dir.exists():
        class_data_dir.mkdir(parents=True)
                
    # prepare the mme model directory
    mme_dir = train_path.parent / "sd_lora"
    shutil.copytree("sd_lora", mme_dir)
    
    
    output_dir = mme_dir / "1" / "output"
    output_dir.mkdir(exist_ok=True)
    
    trn = Trainer(train_path, output_dir)
    
    status = trn.run(
        **tuning_config
    )
    
    
    output_file_name = str(train_path.parent /  f"{str(uuid.uuid4())[:6]}.tar.gz")
    
    with tarfile.open(output_file_name, mode="w:gz") as tar:
        tar.add(mme_dir, arcname="sd_lora")
    
    s3_client.upload_file(output_file_name, s3_bucket, f"{mme_prefix}/{os.path.basename(output_file_name)}")
#     subprocess.run(["/opt/djl/bin/s5cmd", "cp", output_file_name, f"s3://{s3_bucket}/{mme_prefix}/{os.path.basename(output_file_name)}"])
        
    # clean up
    shutil.rmtree(train_path.parent, ignore_errors=True)
    
    return Output().add_as_json({"status":status, "output_location": f"s3://{s3_bucket}/{mme_prefix}/{os.path.basename(output_file_name)}"})
