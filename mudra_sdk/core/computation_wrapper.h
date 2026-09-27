#ifndef COMPUTATION_WRAPPER_H
#define COMPUTATION_WRAPPER_H

#include <memory>
#include <cstdint>
#include "Computation/CommonTypes.h"

#ifdef _WIN32
  #ifdef MUDRA_API_BUILD
    #define MUDRA_API __declspec(dllexport)
  #else
    #define MUDRA_API __declspec(dllimport)
  #endif
#else
  #define MUDRA_API __attribute__((visibility("default")))
#endif

struct ByteBuffer {
  uint8_t* data;
  size_t length;
};

typedef void (*OnRawDataCallback)(uint64_t timestamp, const float* data, int dataLength, int frequency, float frequencyStd);


#ifdef __cplusplus
extern "C" {
#endif

// Opaque pointer to ComputationManager
typedef void* ComputationManagerHandle;

// Two fully independent command tables — see Computation/ProFirmwareCommands.h
// and Computation/UltimateFirmwareCommands.h. `command` is an ordinal into
// the respective product's own FirmwareCommand enum (NOT interchangeable
// between the two calls). A command with no byte template on that product
// returns a zero-length buffer.
MUDRA_API ByteBuffer get_pro_firmware_command(int32_t command);
MUDRA_API ByteBuffer get_ultimate_firmware_command(int32_t command);
MUDRA_API void free_firmware_buffer(uint8_t* buffer);

// CDC (USB serial) ASCII command tokens — see Computation/ProCdcCommands.h
// and Computation/UltimateCdcCommands.h. Returns the raw (non-null-terminated)
// ASCII bytes of the token, or a zero-length buffer if `command` has no CDC
// equivalent on that product. `enable` only matters for the 5 ENABLE_* (power)
// commands, picking their ON vs OFF token; it's ignored for everything else.
MUDRA_API ByteBuffer get_pro_cdc_command_token(int32_t command, bool enable);
MUDRA_API ByteBuffer get_ultimate_cdc_command_token(int32_t command, bool enable);
MUDRA_API void free_cdc_token(uint8_t* buffer);
MUDRA_API bool is_data_needed(ComputationManagerHandle computation, int dataType);
MUDRA_API void set_on_emg_ready(ComputationManagerHandle computation, OnRawDataCallback callback);
MUDRA_API void set_on_imu_h_ready(ComputationManagerHandle computation, OnRawDataCallback callback);
MUDRA_API void set_on_imu_f_ready(ComputationManagerHandle computation, OnRawDataCallback callback);
MUDRA_API void set_on_ppg_ready(ComputationManagerHandle computation, OnRawDataCallback callback);
MUDRA_API void set_parser_emg_resolution(ComputationManagerHandle computation, uint8_t bits);
MUDRA_API void set_parser_emg_channel_count(ComputationManagerHandle computation, uint8_t channels);
MUDRA_API void set_parser_ppg_channel_count(ComputationManagerHandle computation, uint8_t channels);
MUDRA_API void set_parser_imu_h_ranges(ComputationManagerHandle computation, uint8_t accel_range_g, uint16_t gyro_range_dps);
MUDRA_API void set_parser_imu_f_ranges(ComputationManagerHandle computation, uint8_t accel_range_g, uint16_t gyro_range_dps);

// Packet-loss test-mode counters (scale-free — raw channel-0 continuity check).
MUDRA_API void reset_packet_loss_stats(ComputationManagerHandle computation, int dataType);
MUDRA_API void get_packet_loss_stats(ComputationManagerHandle computation, int dataType, uint64_t* samplesSeen, uint64_t* samplesLost);


// Create and destroy the ComputationManager
MUDRA_API ComputationManagerHandle create_computation();
MUDRA_API void delete_computation(ComputationManagerHandle computation);

// Recording functions
MUDRA_API void enable_recording(ComputationManagerHandle computation);
MUDRA_API void disable_recording(ComputationManagerHandle computation);
MUDRA_API bool start_recording(ComputationManagerHandle computation, const Mudra::Computation::RecordingDataType* recordingTypes, int recordingTypesCount, int recordingMaxTime);
MUDRA_API void record_emg_Fusion(ComputationManagerHandle computation, const char* data_tab, const float data);
MUDRA_API void add_video(ComputationManagerHandle computation, const char* key, const char* videoPath);
MUDRA_API void handle_data(ComputationManagerHandle computation, const uint8_t* data, size_t length);
MUDRA_API void stop_recording(ComputationManagerHandle computation);
MUDRA_API bool is_recording_enabled(ComputationManagerHandle computation);
MUDRA_API void record_event(ComputationManagerHandle computation, int eventType, const char* eventName);

// Data retrieval functions
MUDRA_API const char* get_json_recording(ComputationManagerHandle computation);

MUDRA_API void* fill_json_buffer(ComputationManagerHandle computation);
MUDRA_API void free_shared_buffer(void* buffer);
MUDRA_API void save_recording(ComputationManagerHandle computation);

#ifdef __cplusplus
}
#endif

#endif // COMPUTATION_WRAPPER_H
