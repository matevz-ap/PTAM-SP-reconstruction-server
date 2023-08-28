import os
import json
import redis
import shutil
from PIL import Image
import shortuuid
import zipfile
import time

from flask import Flask, request, send_file, make_response
from flask_cors import CORS
from rq import Queue, Worker
from rq.job import Job
from rq.exceptions import NoSuchJobError

from tasks import generate_ptam_task, generate_ply_task, init_reconstruction_task, extend_reconstruction_task, next_best_view_task, reconstruct_mesh_task, texture_task, refine_mesh_task

app = Flask(__name__)
CORS(app, support_credentials=True)

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
conn = redis.from_url(redis_url)
q = Queue(connection=conn)

def _number_of_images(uuid):
    return len([file for file in os.scandir(f"./data/{uuid}/images")])

def save_file(uuid, file, num):
    # num_of_images = _number_of_images(uuid)
    fails = 0
    while fails < 5:
        try:
            file.save(f"data/{uuid}/images/{num}.jpg")
            return
        except:
            print("failed")
            fails += 1
            time.sleep(1)

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

def exists_job(uuid):
    for job in q.jobs:
        if not job.is_finished and job.args[0] == uuid:
            return job
    for w in Worker.all(queue=q):
        job = w.get_current_job()
        if job and job.args[0] == uuid:
            return job
    return None

def enqueue_job(function, *args, **kwargs):
    if job := exists_job(args[0]):
        return q.enqueue(function, *args, **kwargs, depends_on=job)
    return q.enqueue(function, *args, **kwargs)

@app.route("/init", methods=["POST"])
def initialize_reconstruction():
    if "image" not in request.files:
        return "Missing requred request paramater: 'image' of type file", 400
    
    uuid = shortuuid.uuid()
    image = request.files['image']
    os.system(f"mkdir -p data/{uuid}/images")
    os.system(f"mkdir -p data/{uuid}/results")
    conn.set(uuid, 1)

    save_file(uuid, image, 0)
    focal = request.form.get("focal", 6000)
    get_camera_settings(uuid, Image.open(image), focal or 6000)
    return uuid

@app.route("/<uuid>/extend", methods=["POST"])
def extend_reconstruction(uuid):
    if "image" not in request.files:
        return "Missing requred reques paramater: 'image' of type file", 400

    num_of_images = int(conn.get(uuid).decode())
    save_file(uuid, request.files['image'], num_of_images)
    if num_of_images == 1:
        conn.set(uuid, num_of_images + 1)
        job = enqueue_job(init_reconstruction_task, uuid)
    else:
        job = enqueue_job(extend_reconstruction_task, uuid, num_of_images + 1)
        conn.set(uuid, num_of_images + 1)

    return job.get_id()

@app.route("/<uuid>/reconstruct_mesh", methods=["GET"])
def reconstruct_mesh(uuid):
    job = enqueue_job(reconstruct_mesh_task, uuid)
    return job.get_id()

@app.route("/<uuid>/next_best_view", methods=["GET"])
def next_best_view(uuid):
    job = enqueue_job(next_best_view_task, uuid)
    return job.get_id()

@app.route("/<uuid>/texture", methods=["GET"])
def texture(uuid):
    job = enqueue_job(texture_task, uuid)
    return job.get_id()

@app.route("/<uuid>/generate/ply", methods=["GET"])
def generate_ply(uuid):
    job = enqueue_job(generate_ply_task, uuid)
    return job.get_id()

@app.route("/<uuid>/generate/ptam", methods=["GET"])
def generate_ptam(uuid):
    job = enqueue_job(generate_ptam_task, uuid)
    return job.get_id()

@app.route("/<uuid>/download_or_generate/ply", methods=["GET"])
def download_or_generate_ply(uuid):
    try:
        return send_file(f"./data/{uuid}/ply.ply")
    except FileNotFoundError:
        job = enqueue_job(texture_task, uuid)
        return job.get_id(), 404

@app.route("/<uuid>/download/ply", methods=["GET"])
def download_ply(uuid):
    try:
        return send_file(f"./data/{uuid}/results/ply.ply")
    except FileNotFoundError:
        return "No ply file", 404
        
@app.route("/<uuid>/download/texture", methods=["GET"])
def download_texture(uuid):
    # img = Image.open(f"./data/{uuid}/results/ply.png")
    # wpercent = (300/float(img.size[0]))
    # hsize = int((float(img.size[1])*float(wpercent)))
    # img = img.resize((300,hsize), Image.Resampling.LANCZOS)
    # img.save(f"./data/{uuid}/results/ply_resize.png", format='PNG')
    # return make_response(send_file(f"./data/{uuid}/results/ply_resize.png"))
    return send_file(f"./data/{uuid}/results/ply.png")

@app.route("/<uuid>/download/mvs", methods=["GET"])
def download_mvs(uuid):
    return send_file(f"./data/{uuid}/scene.mvs")

@app.route("/<uuid>/download/ptam", methods=["GET"])
def download_ptam(uuid):
    return send_file(f"./data/{uuid}/installer")

@app.route("/<uuid>/refine", methods=["GET"])
def refine_mesh(uuid):
    job = enqueue_job(refine_mesh_task, uuid, job_timeout=3600)
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
    with open(f"./data/{uuid}/results.zip", "wb") as f:
        f.write(request.data)

    with zipfile.ZipFile(f"./data/{uuid}/results.zip", 'r') as zip_ref:
        zip_ref.extractall(f"./data/{uuid}/results")
    return "OK", 200

@app.route("/get_focal", methods=['POST'])
def get_focal():
    image = request.files['image']
    image = Image.open(image)
    focal = image.getexif().get_ifd(0x8769).get(37386, 0)
    return make_response(json.dumps({"focal": int(focal * 1000) or None}))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)