import requests
import subprocess
import time
import matplotlib.pyplot as plt

uuids = []
jobs = []
recon = []

start = time.time()
for i in range(0, 100):
    with open("./dataset/opeka/images/frame000.jpg", "rb") as f:
        res = requests.post("http://127.0.0.1:5000/init", files={"image": f})
        uuid = res.text 
        uuids.append(uuid)

    with open("./dataset/opeka/images/frame001.jpg", "rb") as f:
        res = requests.post(f"http://127.0.0.1:5000/{uuid}/extend", files={"image": f})
        jobs.append(res.text)

while True:
    res = requests.get(f"http://127.0.0.1:5000/results/{jobs[-1]}")
    res = res.json()
    if res["status"] != "in_progress":
        break
end = time.time()


for job in jobs:
    res = requests.get(f"http://127.0.0.1:5000/results/{job}") 
    recon.append(res.json()) 

for uuid in uuids: # delete folders with reconstruction
    subprocess.run(f"rm -r ./data/{uuid}", shell=True)

print("Skupno", end - start)
print("Povrecje", sum([r["duration"]for r in recon]) / len(recon))
plt.plot(range(0, len(recon)), [r["duration"]for r in recon], '-ok')
plt.xlabel('Zaporedna inicializacija')
plt.ylabel('Cas inicializacije (sekunde)')
plt.grid()
plt.show()

