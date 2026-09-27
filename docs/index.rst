Mudra Pro SDK
=============

The **Mudra SDK** (``mudra_sdk``) is a Python library for the **Mudra Pro** and
**Mudra Ultimate** wrist-worn sensor devices by Wearable Devices. It presents
one unified, ``asyncio``-based API over two physically different transports —
**BLE** (Bluetooth Low Energy) and **USB-CDC** (serial) — for four sensor
streams (EMG, hand IMU, finger IMU, PPG), SD-card recording, firmware update,
and account sign-in/device licensing.

The SDK is built for two audiences:

- **External developers** building applications and research workflows on top
  of Mudra Pro / Mudra Ultimate.
- **AI coding agents** integrating the SDK on a developer's behalf — every
  guide page doubles as a reference an agent can integrate against directly.

How the pieces fit
------------------

- **Connecting to a device never requires an account** — a signed-out app
  still connects and streams, at whatever license tier (``FREE``/``PLUS``/
  ``PRO``) the device already holds. Sign-in (:doc:`AUTH`) is what *raises*
  that tier; it is orthogonal to connecting at all.
- **`Mudra` is a process-wide singleton** that owns both transports and fans
  every device event out to one registered delegate; **`MudraDevice`** is
  transport-agnostic from the caller's side (:doc:`SDK_USAGE`).
- **BLE and CDC differ in readiness, not in API shape** — CDC needs an
  explicit ``START`` after connecting where BLE doesn't; every typed method
  already branches internally so callers rarely need to check
  ``device.transport`` themselves (:doc:`CONNECTION`).

Pick your path
---------------

.. raw:: html

   <div class="ex-index">
     <a class="ex-index-item" href="installation.html">
       <span class="ex-index-head"><span class="ex-index-name">Installation</span></span>
       <span class="ex-index-desc">Dependencies, native library, and how to import the SDK with no PyPI package yet.</span>
     </a>
     <a class="ex-index-item" href="getting_started.html">
       <span class="ex-index-head"><span class="ex-index-name">Quickstart</span></span>
       <span class="ex-index-desc">Scan, connect, and stream EMG in about a dozen lines.</span>
     </a>
     <a class="ex-index-item" href="SDK_USAGE.html">
       <span class="ex-index-head"><span class="ex-index-name">Usage guide</span></span>
       <span class="ex-index-desc">Package layout, core architecture (Mudra / MudraDevice / MudraDelegate), key enums.</span>
     </a>
     <a class="ex-index-item" href="examples.html">
       <span class="ex-index-head"><span class="ex-index-name">Examples</span></span>
       <span class="ex-index-desc">The runnable reference app: scan, connect, live sensors, config, SD recording, firmware update, auth.</span>
     </a>
     <a class="ex-index-item" href="api_reference.html">
       <span class="ex-index-head"><span class="ex-index-name">API reference</span></span>
       <span class="ex-index-desc">The full <code>mudra_sdk</code> reference: Mudra, MudraDevice, enums, callbacks, auth.</span>
     </a>
     <a class="ex-index-item" href="AUTH.html">
       <span class="ex-index-head"><span class="ex-index-name">Auth &amp; licensing</span></span>
       <span class="ex-index-desc">Sign-in, device license tiers, and why streaming works fine without either.</span>
     </a>
   </div>

.. toctree::
   :maxdepth: 2
   :caption: Get started

   installation
   getting_started
   supported_devices

.. toctree::
   :maxdepth: 2
   :caption: Guides

   SDK_USAGE
   CONNECTION
   SENSORS
   CALLBACKS
   AUTH
   examples

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api_reference
   data_format

.. toctree::
   :maxdepth: 2
   :caption: Under the hood

   native_library
   troubleshooting
   faq

Indices
-------

* :ref:`genindex`
* :ref:`search`
