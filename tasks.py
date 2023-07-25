import json
import subprocess
import re

def make_response(uuid, numbers, success, output=None):
    try:
        return json.dumps({
            "reconstruction_id": uuid,
            "success": success, 
            "duration": numbers[0],
            "views": numbers[1],
            "estimated_views": numbers[2],
            "tracks": numbers[3],
            "estimated_tracks": numbers[4],
            "status": "finished",
            "vertices": numbers[12] if len(numbers) > 10 else 0,
            "faces": numbers[13] if len(numbers) > 10 else 0,
            "output": output or "",
        })
    except BaseException:
        return json.dumps({"status": "finished", "success": success, "output": output or ""})


def init_reconstruction_task(uuid):
    command = f"cd build/; ./reconstruction_cli init ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    numbers = re.findall("[-+]?(?:\d*\.\d+|\d+)", output)
    print(output)
    if len(numbers) > 1: 
        numbers.pop(1)
    return make_response(uuid, list(map(float, numbers)), "Initialization successful" in output, output)
    

def extend_reconstruction_task(uuid, number_of_images):
    command = f"cd build/; ./reconstruction_cli extend ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid} {number_of_images - 1}"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    print(output)
    numbers = re.findall("[-+]?(?:\d*\.\d+|\d+)", output)
    return make_response(uuid, list(map(float, numbers)), "Extend successful" in output, output)

def reconstruct_mesh_task(uuid):
    command = f"cd build/; ./reconstruction_cli reconstruct_mesh ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    return json.dumps({
        "finished": True,
        "reconstruction_id": uuid,
    })

def texture_task(uuid):
    command = f"cd build/; ./reconstruction_cli texture ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    return json.dumps({
            "finished": True,
            "reconstruction_id": uuid,
        })


def generate_ply_task(uuid):
    command = f"cd build/; ./reconstruction_cli download ply ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    return {
        "succes": True,
        "reconstruction_id": uuid,
    }


def generate_ptam_task(uuid):
    command = f"cd build/; ./reconstruction_cli ptam ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    print(output)
    return json.dumps({
            "finished": True,
            "reconstruction_id": uuid,
        })

def next_best_view_task(uuid):
    command = f"cd build/; ./reconstruction_cli nbv ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    print(output)
    return json.dumps({
            "finished": True,
            "reconstruction_id": uuid,
        })

def refine_mesh_task(uuid):
    command = f"cd build/; ./reconstruction_cli refine ../data/{uuid}/images/ ../data/{uuid}/camera_settings.txt ../data/{uuid}/"
    output = subprocess.run(command, capture_output=True, shell=True).stdout.decode()
    print(output)
    return json.dumps({
            "finished": True,
            "reconstruction_id": uuid,
        })