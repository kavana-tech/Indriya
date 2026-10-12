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

.. The exclude list hides the transport-service hooks BleService/CdcService
   call on Mudra — not for application code.

.. autoclass:: mudra_sdk.models.mudra.Mudra
   :members:
   :show-inheritance:
   :exclude-members: on_ble_characteristic_discovered, on_charging_state_changed,
                     on_data_received, on_battery_level_changed,
                     on_sensor_status_received, on_storage_record_state_received,
                     on_storage_record_error_received, on_storage_next_file_num_received,
                     on_command_error_received, on_ping_response_received,
                     on_device_info_received, on_firmware_version_received,
                     on_command_reply_received, on_device_discovered,
                     on_mudra_device_disconnected, on_mudra_device_disconnecting,
                     on_mudra_device_connected, on_mudra_device_connecting,
                     on_mudra_device_connection_failed, on_bluetooth_state_changed

MudraDevice
-----------

One object per physical device, valid for either transport. Every method
already branches internally on ``device.transport`` and picks the right wire
format — see :doc:`CONNECTION` for what differs per transport under the
hood.

.. The exclude list hides hooks the SDK itself calls during connect/disconnect
   and data dispatch — not for application code.

.. autoclass:: mudra_sdk.models.mudra_device.MudraDevice
   :members:
   :show-inheritance:
   :exclude-members: handle_disconnection, update_connection_properties,
                     on_characteristic_discovered, on_cdc_ready, start_streaming,
                     stop_streaming, on_charging_state_changed, on_data_received,
                     on_battery_level_changed, on_sensor_status_received,
                     on_storage_record_state_received, on_storage_record_error_received,
                     on_storage_next_file_num_received, on_command_error_received,
                     on_ping_response_received, on_device_info_received,
                     on_firmware_version_received

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

The status and info dataclasses delivered to status/info callbacks and
returned by the cached ``get_*_info()`` getters (:doc:`SENSORS`, :doc:`AUTH`,
:doc:`CALLBACKS`), plus two supporting types: ``FirmwareDetails`` (constants)
and ``CdcDevice`` (a USB-CDC device's identity).

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

   .. note::

      These constants are for the **Mudra Band**, not Mudra Pro or Mudra
      Ultimate. The firmware versions this SDK supports for Mudra Pro and
      Mudra Ultimate are listed in :doc:`supported_devices` (and in
      ``supported_firmware.json`` at the root of the SDK).

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

.. module:: mudra_sdk.auth

Sign in with :func:`sign_in_email` **before** connecting: while signed in, the
SDK itself calls :func:`provision_device` and :func:`provision_user_id` on
every connect, and the device's ``LicenseManager`` renews the license before
it expires. Call them yourself only if you sign in after a device is already
connected; both do nothing while signed out.

The signed-in tier and ``uref`` are kept in memory, per process — after a
restart, call :func:`sign_in_email` again before provisioning does anything.
The cloud client's access/refresh tokens, however, **are written to disk**
(``~/.mudra_sdk/auth_storage.json``) and :func:`logout` does not remove them,
so ``MudraServerClient`` calls keep working after ``logout()`` and in a new process.
To sign out fully, also call ``AuthStorage().clear()``
(``from mudra_sdk.cloud import AuthStorage``).

.. autofunction:: mudra_sdk.auth.sign_in_email

.. autofunction:: mudra_sdk.auth.logout

.. autofunction:: mudra_sdk.auth.get_user_ref

.. autofunction:: mudra_sdk.auth.provision_device

.. autofunction:: mudra_sdk.auth.provision_user_id

Lab Streaming Layer
--------------------

:mod:`mudra_sdk.lsl` — publish a connected device's sensors as LSL streams.
See :doc:`LSL` for the guide (stream layout, timestamps, reconfiguring and
reconnecting). ``pylsl`` is optional: importing the package never requires
it, only starting a bridge does.

.. autoclass:: mudra_sdk.lsl.bridge.MudraLslBridge
   :members:

.. autoclass:: mudra_sdk.lsl.clock.DeviceClockMapper
   :members:

.. autodata:: mudra_sdk.lsl.clock.GRTC_CPS

.. automodule:: mudra_sdk.lsl.metadata
   :members: SENSOR_KEYS, SensorSpec, IMU_CHANNELS, PPG_CHANNELS, normalize_sensors, channels

.. These carry no ``#:`` doc comment in the source, so autodoc's ``:members:``
   skips them (and ``autodata`` would show the str/dict builtin docstring);
   describe them by hand.

.. data:: mudra_sdk.lsl.metadata.EMG
   :value: 'emg'

   Sensor key for EMG.

.. data:: mudra_sdk.lsl.metadata.IMU_HAND
   :value: 'imu_hand'

   Sensor key for the hand IMU (``H_IMU``).

.. data:: mudra_sdk.lsl.metadata.IMU_RING
   :value: 'imu_ring'

   Sensor key for the finger IMU (``F_IMU``, Mudra Ultimate only).

.. data:: mudra_sdk.lsl.metadata.PPG_H
   :value: 'ppg_h'

   Sensor key for the hand PPG (``PPG_H``).

.. data:: mudra_sdk.lsl.metadata.PPG_F
   :value: 'ppg_f'

   Sensor key for the finger (ring) PPG (``PPG_F``).

.. data:: mudra_sdk.lsl.metadata.SENSORS
   :type: dict[str, SensorSpec]

   The :class:`SensorSpec` for each sensor key.

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

   Owned one-per-device; the SDK starts it on connect and stops it on
   disconnect for you (see :doc:`AUTH`). It periodically re-provisions the
   license token before it expires — which fetches a fresh token from the
   server, so renewal only happens while signed in
   (:func:`mudra_sdk.auth.sign_in_email`). You don't call it yourself.

.. autoclass:: mudra_sdk.models.data_recorder.DataRecorder
   :members:

   Backs ``device.start_recording()``/``stop_recording()``/
   ``get_json_recording()`` — the host-side (non-SD) JSON recorder. Use the
   ``MudraDevice`` methods, not this class directly.
