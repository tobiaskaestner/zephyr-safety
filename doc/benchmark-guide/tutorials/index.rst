Tutorials
=========

A tutorial is a lesson. You do the steps, and you get a working result.

.. toctree::
   :maxdepth: 1

The guide has no tutorials yet. Until then, the section below gives the
commands of a typical session.

Typical session
---------------

.. code-block:: console

   # on the lab host: make the lab space (once)
   mkdir ~/lab && cd ~/lab
   git clone <safety repository> safety
   python3 -m venv .venv
   .venv/bin/pip install -r safety/scripts/benchmarks/requirements.lock
   .venv/bin/python safety/scripts/benchmarks/study.py lab init --repo safety --sdk ~/zephyr-sdk-1.0.1
   # from now on, any study.py in the lab folder runs the study.py of safety/ with .venv
   study.py trees setup ws-safety ws-up
   study.py lab status
   # run all experiments of a study
   study.py campaign check <repo>/validation/empirical/latencies/st-default-latencies
   study.py campaign run <repo>/validation/empirical/latencies/st-default-latencies --detach
   study.py campaign status
   study.py lab export -o lab.tar.gz --campaign <id>

   # on the analysis host (another lab space), with lab.tar.gz and lab.tar.gz.sha256
   study.py lab import lab.tar.gz
   study.py analysis build results/kernel-latency
   study.py analysis html results/kernel-latency
