import os
import json
import redis
import shutil
from PIL import Image
import shortuuid
import zipfile

from flask import Flask, request, send_file, make_response
from flask_cors import CORS
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError

from tasks import generate_ptam_task, generate_ply_task, init_reconstruction_task, extend_reconstruction_task, next_best_view_task, reconstruct_mesh_task, texture_task, refine_mesh_task

app = Flask(__name__)
CORS(app, support_credentials=True)

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)
q = Queue(connection=conn)

def _number_of_images(uuid):
    return len([file for file in os.scandir(f"data/{uuid}/images")])

def save_file(uuid, file):
    num_of_images = _number_of_images(uuid)
    file.save(f"data/{uuid}/images/{num_of_images}.jpg")

def get_camera_settings(uuid, image, focal):
    with open(f"data/{uuid}/camera_settings.txt", 'a') as file:
        width, height = image.size
        file.write(f"{width}\n")
        file.write(f"{height}\n")
        file.write(f"{focal}\n")
        file.write(f"{width / 2}\n")
        file.write(f"{height / 2}\n")
        file.write("1.0\n") # aspect ratio
        file.write("0.0\n\n") # skew

@app.route("/init", methods=["POST"])
def initialize_reconstruction():
    if "image" not in request.files:
        return "Missing requred request paramater: 'image' of type file", 400
    
    uuid = shortuuid.uuid()
    image = request.files['image']
    os.system(f"mkdir -p data/{uuid}/images")
    save_file(uuid, image)
    focal = request.form.get("focal", 6000)
    get_camera_settings(uuid, Image.open(image), focal or 6000)
    return uuid

@app.route("/<uuid>/extend", methods=["POST"])
def extend_reconstruction(uuid):
    if "image" not in request.files:
        return "Missing requred reques paramater: 'image' of type file", 400

    save_file(uuid, request.files['image'])

    number_of_images = _number_of_images(uuid)
    if  number_of_images == 2: # also needs check that init is not in progress
        job = q.enqueue(init_reconstruction_task, uuid)
    else:
        job = q.enqueue(extend_reconstruction_task, uuid, number_of_images)

    return job.get_id()

@app.route("/<uuid>/reconstruct_mesh", methods=["GET"])
def reconstruct_mesh(uuid):
    job = q.enqueue(reconstruct_mesh_task, uuid)
    return job.get_id()

@app.route("/<uuid>/next_best_view", methods=["GET"])
def next_best_view(uuid):
    job = q.enqueue(next_best_view_task, uuid)
    return job.get_id()

@app.route("/<uuid>/texture", methods=["GET"])
def texture(uuid):
    job = q.enqueue(texture_task, uuid)
    return job.get_id()

@app.route("/<uuid>/generate/ply", methods=["GET"])
def generate_ply(uuid):
    job = q.enqueue(generate_ply_task, uuid)
    return job.get_id()

@app.route("/<uuid>/generate/ptam", methods=["GET"])
def generate_ptam(uuid):
    job = q.enqueue(generate_ptam_task, uuid)
    return job.get_id()

@app.route("/<uuid>/download_or_generate/ply", methods=["GET"])
def download_or_generate_ply(uuid):
    try:
        return send_file(f"./data/{uuid}/ply.ply")
    except FileNotFoundError:
        job = q.enqueue(texture_task, uuid)
        return job.get_id(), 404

@app.route("/<uuid>/download/ply", methods=["GET"])
def download_ply(uuid):
    try:
        return send_file(f"./data/{uuid}/ply.ply")
    except FileNotFoundError:
        return "No ply file", 404
        
@app.route("/<uuid>/download/texture", methods=["GET"])
def download_texture(uuid):
    response = make_response(send_file(f"./data/{uuid}/ply.png"))
    return response

@app.route("/<uuid>/download/mvs", methods=["GET"])
def download_mvs(uuid):
    return send_file(f"./data/{uuid}/scene.mvs")

@app.route("/<uuid>/download/ptam", methods=["GET"])
def download_ptam(uuid):
    return send_file(f"./data/{uuid}/installer")

@app.route("/<uuid>/refine", methods=["GET"])
def refine_mesh(uuid):
    job = q.enqueue(refine_mesh_task, args=(uuid,), job_timeout=3600)
    return job.get_id()

@app.route("/<uuid>/file_availability/<file_name>", methods=["GET"])
def file_availability(uuid, file_name):
    return json.dumps(os.path.exists(f"./data/{uuid}/{file_name}"))

@app.route("/online", methods=["GET"])
def online():
    return "OK", 200

@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):
    try:
        job = Job.fetch(job_key, connection=conn)
    except NoSuchJobError:
        return json.dumps({"status": "does_not_exist"}), 202

    if job.is_finished:
        return json.loads(job.result), 200
    else:
        return json.dumps({"status": "in_progress"}), 202
        
@app.route("/<uuid>/download", methods=['GET'])
def download(uuid):
    folder_path = f"./data/{uuid}"
    shutil.make_archive(folder_path, 'zip', folder_path)

    with open(f"{folder_path}.zip", 'rb') as f:
        data = f.read()
    response = make_response(data)
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename={uuid}.zip'
    return response

@app.route("/<uuid>/upload", methods=['POST'])
def upload(uuid):
    with open(f"./data/{uuid}.zip", "wb") as f:
        f.write(request.data)

    with zipfile.ZipFile(f"./data/{uuid}.zip", 'r') as zip_ref:
        zip_ref.extractall(f"./data/{uuid}")
    return "OK", 200

@app.route("/get_focal", methods=['POST'])
def get_focal():
    image = request.files['image']
    image = Image.open(image)
    focal = image.getexif().get_ifd(0x8769).get(37386, 0)
    return make_response(json.dumps({"focal": int(focal * 1000) or None}))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)