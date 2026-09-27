API reference
=============

The public surface is re-exported from the package root:

.. code-block:: python

   from mudra_sdk import (
       Mudra, MudraDevice, MudraPro, MudraUltimate, MudraModel,
       FirmwareCallbacks, FirmwareDetails,
   )

Everything below is generated from the SDK's own docstrings — see
:doc:`SDK_USAGE`, :doc:`CONNECTION`, :doc:`SENSORS`, :doc:`CALLBACKS`, and
:doc:`AUTH` for narrative guides with runnable examples over this same API.

Mudra
-----

The process-wide singleton — ``Mudra()`` always returns the same instance.
Owns both transports and dispatches every device event to the registered
:class:`~mudra_sdk.models.callbacks.MudraDelegate`.

.. autoclass:: mudra_sdk.models.mudra.Mudra
   :members:
   :show-inheritance:

MudraDevice
-----------

One object per physical device, valid for either transport. Every method
already branches internally on ``device.transport`` and picks the right wire
format — see :doc:`CONNECTION` for what differs per transport under the
hood.

.. autoclass:: mudra_sdk.models.mudra_device.MudraDevice
   :members:
   :show-inheritance:

Per-model subclasses
~~~~~~~~~~~~~~~~~~~~~

You never construct these directly — the SDK detects the model and hands
you the right one. See :doc:`supported_devices` for what differs between
them.

.. autoclass:: mudra_sdk.models.mudra_pro.MudraPro
   :members:
   :show-inheritance:

.. autoclass:: mudra_sdk.models.mudra_ultimate.MudraUltimate
   :members:
   :show-inheritance:

Status & data types
--------------------

Dataclasses returned via status/info callbacks (:doc:`SENSORS`, :doc:`AUTH`,
:doc:`CALLBACKS`).

.. autoclass:: mudra_sdk.models.mudra_device.EmgStatus
   :members:

.. autoclass:: mudra_sdk.models.mudra_device.ImuStatus
   :members:

.. autoclass:: mudra_sdk.models.mudra_device.PpgStatus
   :members:

.. autoclass:: mudra_sdk.models.mudra_device.RecordStatus
   :members:

.. autoclass:: mudra_sdk.models.mudra_device.LicenseDeviceInfo
   :members:

.. autoclass:: mudra_sdk.models.mudra_device.FirmwareVersion
   :members:

.. autoclass:: mudra_sdk.models.firmware_details.FirmwareDetails
   :members:

.. autoclass:: mudra_sdk.models.cdc_device.CdcDevice
   :members:

Callbacks
---------

The global delegate ABC you implement once and register via
``Mudra().set_delegate(...)`` — see :doc:`CALLBACKS` for the full reference
including every per-device ``set_on_*`` setter (those live directly on
:class:`~mudra_sdk.models.mudra_device.MudraDevice`, documented above).

.. autoclass:: mudra_sdk.models.callbacks.MudraDelegate
   :members:
   :show-inheritance:

Enums
-----

The identifiers and value sets used throughout the API — see
:doc:`SDK_USAGE` §5 ("Quick reference — key enums") for a condensed table
with usage context.

Sensor identity
~~~~~~~~~~~~~~~~

.. autoclass:: mudra_sdk.models.enums.SensorTypes
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.FirmwareDataType
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.RecordingDataType
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.EventType
   :members:
   :undoc-members:

EMG / IMU / PPG configuration ranges
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: mudra_sdk.models.enums.EmgRes
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.ProEMGODR
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.UltimateEMGODR
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.IMUODR
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.IMUAccRange
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.IMUGyrRange
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.PPGODR
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.PPGChannelCount
   :members:
   :undoc-members:

Model, licensing & command status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: mudra_sdk.models.enums.MudraModel
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.LicenseTier
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.FirmwareCallbacks
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.BtCmdId
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.BtCmdStatus
   :members:
   :undoc-members:

Firmware command tables
~~~~~~~~~~~~~~~~~~~~~~~~

Every known firmware command, per model, with its numeric op-code — useful
for building raw frames (:doc:`CONNECTION` §4) or logging. These are large;
most callers won't need to browse them directly.

.. autoclass:: mudra_sdk.models.enums.ProFirmwareCommand
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.models.enums.UltimateFirmwareCommand
   :members:
   :undoc-members:

Account sign-in & licensing
----------------------------

:mod:`mudra_sdk.auth` — see :doc:`AUTH` for the full guide (why this matters,
the two independent halves, a practical checklist).

.. automodule:: mudra_sdk.auth
   :members:

Firmware update (DFU)
----------------------

The public exception/stage surface behind ``device.start_dfu(...)`` — see
:doc:`CONNECTION` §6.

.. autoclass:: mudra_sdk.service.dfu_service.DfuStage
   :members:
   :undoc-members:

.. autoclass:: mudra_sdk.service.dfu_service.DfuError
   :members:
   :show-inheritance:

Advanced / internal
--------------------

You don't call these directly in normal use — documented here for anyone
extending the SDK itself.

.. autoclass:: mudra_sdk.models.license_manager.LicenseManager
   :members:

   Owned one-per-device, started on connect and stopped on disconnect (see
   :doc:`AUTH`) — periodically re-provisions the license token before it
   expires. Nothing to call; nothing to configure.

.. autoclass:: mudra_sdk.models.data_recorder.DataRecorder
   :members:

   Backs ``device.start_recording()``/``stop_recording()``/
   ``get_json_recording()`` — the host-side (non-SD) JSON recorder. Use the
   ``MudraDevice`` methods, not this class directly.
