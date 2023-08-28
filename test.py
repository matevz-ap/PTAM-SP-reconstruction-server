import requests
import subprocess
import time
import matplotlib.pyplot as plt
from multiprocessing import Process

def rec(process_id):
    jobs = []
    uuid = ""
    start = time.time()
    with open("./dataset/grad/images/frame000.jpg", "rb") as f:
        res = requests.post("http://127.0.0.1:5000/init", files={"image": f})
        uuid = res.text 
        print(uuid)
    
    for i in range(1, 3):
        time.sleep(1)
        with open(f"./dataset/grad/images/frame00{str(i)}.jpg", "rb") as f:
            res = requests.post(f"http://127.0.0.1:5000/{uuid}/extend", files={"image": f})
            jobs.append(res.text)

    while True:
        res = requests.get(f"http://127.0.0.1:5000/results/{jobs[-1]}")
        res = res.json()
        if res["status"] not in ("in_progress", "does_not_exist"):
            break
        time.sleep(1)
    end = time.time()
    recon = [requests.get(f"http://127.0.0.1:5000/results/{job}").json() for job in jobs]
    print(recon)
    # print("recon: ", [r["duration"] for r in recon])
    print(f"Time - {process_id}: ", end - start)

procs = []
for i in range(0, 5):
    proc = Process(target=rec, args=(i,))
    procs.append(proc)
    proc.start()
    time.sleep(1)


for proc in procs:
    proc.join()

# recon = [requests.get(f"http://127.0.0.1:5000/results/{job}").json() for job in jobs]

# for uuid in uuids: # delete folders with reconstruction
#     subprocess.run(f"rm -r ./data/{uuid}", shell=True)

# print("Skupno", end - start)
# print("Povrecje", sum([r["duration"]for r in recon]) / len(recon))
# plt.plot(range(0, len(recon)), [r["duration"]for r in recon], '-ok')
# plt.xlabel('Zaporedna inicializacija')
# plt.ylabel('Cas inicializacije (sekunde)')
# plt.grid()
# plt.show()
