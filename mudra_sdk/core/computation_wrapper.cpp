#include "computation_wrapper.h"
#include "Computation/ComputationManager.h"
#include "Computation/Logging.h"
#include "Computation/ProFirmwareCommands.h"
#include "Computation/UltimateFirmwareCommands.h"
#include "Computation/ProCdcCommands.h"
#include "Computation/UltimateCdcCommands.h"

#include <string>
#include <memory>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <vector>

using namespace Mudra::Computation;

static std::shared_ptr<Logger> logger = std::make_shared<Logger>("Mudra", Logger::Severity::Error);
static std::shared_ptr<Pro::ProFirmwareCommands> proFirmwareCommands = std::make_shared<Pro::ProFirmwareCommands>();
static std::shared_ptr<Ultimate::UltimateFirmwareCommands> ultimateFirmwareCommands = std::make_shared<Ultimate::UltimateFirmwareCommands>();
static std::shared_ptr<Pro::ProCdcCommands> proCdcCommands = std::make_shared<Pro::ProCdcCommands>();
static std::shared_ptr<Ultimate::UltimateCdcCommands> ultimateCdcCommands = std::make_shared<Ultimate::UltimateCdcCommands>();

static ByteBuffer make_string_buffer(const std::string& s) {
    size_t len = s.size();
    uint8_t* buffer = (uint8_t*)malloc(len > 0 ? len : 1);
    if (!buffer) {
        return { nullptr, 0 };
    }
    if (len > 0) {
        memcpy(buffer, s.data(), len);
    }
    return { buffer, len };
}

static ByteBuffer make_command_buffer(const std::vector<uint8_t>& vec) {
    size_t len = vec.size();
    if (len == 0) {
        return { nullptr, 0 };
    }
    uint8_t* buffer = (uint8_t*)malloc(len);
    if (!buffer) {
        return { nullptr, 0 };
    }
    memcpy(buffer, vec.data(), len);
    return { buffer, len };
}

extern "C" {

    MUDRA_API ByteBuffer get_pro_firmware_command(int32_t command) {
        return make_command_buffer(
            proFirmwareCommands->getCommandBytes(static_cast<Pro::ProFirmwareCommands::FirmwareCommand>(command)));
    }

    MUDRA_API ByteBuffer get_ultimate_firmware_command(int32_t command) {
        return make_command_buffer(
            ultimateFirmwareCommands->getCommandBytes(static_cast<Ultimate::UltimateFirmwareCommands::FirmwareCommand>(command)));
    }

    MUDRA_API void free_firmware_buffer(uint8_t* buffer) {
        if (buffer) free(buffer);
    }

    MUDRA_API ByteBuffer get_pro_cdc_command_token(int32_t command, bool enable) {
        return make_string_buffer(proCdcCommands->getCommandToken(static_cast<Pro::ProCdcCommands::FirmwareCommand>(command), enable));
    }

    MUDRA_API ByteBuffer get_ultimate_cdc_command_token(int32_t command, bool enable) {
        return make_string_buffer(ultimateCdcCommands->getCommandToken(static_cast<Ultimate::UltimateCdcCommands::FirmwareCommand>(command), enable));
    }

    MUDRA_API void free_cdc_token(uint8_t* buffer) {
        if (buffer) free(buffer);
    }

    MUDRA_API bool is_data_needed(ComputationManagerHandle computation, int dataType) {
        if (computation) {
            return static_cast<ComputationManager*>(computation)->IsDataNeeded((FirmwareDataType)dataType);
        }
        return false;
    }

    MUDRA_API void set_on_emg_ready(ComputationManagerHandle computation, OnRawDataCallback callback) {
        if (!computation) {
            return;
        }
        ComputationManager* manager = static_cast<ComputationManager*>(computation);
        if (callback == nullptr) {
            manager->SetOnEmgPackageReadyCallBack(nullptr);
            return;
        }
        manager->SetOnEmgPackageReadyCallBack([callback](EmgPackageData& package) {
            std::vector<float> flattened;
            for (int ch = 0; ch < package.channelCount; ++ch) {
                flattened.insert(flattened.end(), package.data[ch].begin(), package.data[ch].end());
            }
            callback(
                package.timeStamp,
                flattened.data(),
                static_cast<int>(flattened.size()),
                static_cast<int>(package.frequency),
                package.frequencyStd);
        });
    }

    MUDRA_API void set_on_imu_h_ready(ComputationManagerHandle computation, OnRawDataCallback callback) {
        if (!computation) {
            return;
        }
        ComputationManager* manager = static_cast<ComputationManager*>(computation);
        if (callback == nullptr) {
            manager->SetOnImuHPackageReadyCallBack(nullptr);
            return;
        }
        manager->SetOnImuHPackageReadyCallBack([callback](ImuPackageData& package) {
            std::vector<float> flattened;
            for (unsigned axis = 0; axis < 6; ++axis) {
                flattened.insert(flattened.end(), package.data[axis].begin(), package.data[axis].end());
            }
            callback(
                package.timeStamp,
                flattened.data(),
                static_cast<int>(flattened.size()),
                static_cast<int>(package.frequency),
                package.frequencyStd);
        });
    }

    MUDRA_API void set_on_imu_f_ready(ComputationManagerHandle computation, OnRawDataCallback callback) {
        if (!computation) {
            return;
        }
        ComputationManager* manager = static_cast<ComputationManager*>(computation);
        if (callback == nullptr) {
            manager->SetOnImuFPackageReadyCallBack(nullptr);
            return;
        }
        manager->SetOnImuFPackageReadyCallBack([callback](ImuPackageData& package) {
            std::vector<float> flattened;
            for (unsigned axis = 0; axis < 6; ++axis) {
                flattened.insert(flattened.end(), package.data[axis].begin(), package.data[axis].end());
            }
            callback(
                package.timeStamp,
                flattened.data(),
                static_cast<int>(flattened.size()),
                static_cast<int>(package.frequency),
                package.frequencyStd);
        });
    }

    MUDRA_API void set_on_ppg_ready(ComputationManagerHandle computation, OnRawDataCallback callback) {
        if (!computation) {
            return;
        }
        ComputationManager* manager = static_cast<ComputationManager*>(computation);
        if (callback == nullptr) {
            manager->SetOnPpgPackageReadyCallBack(nullptr);
            return;
        }
        manager->SetOnPpgPackageReadyCallBack([callback](PpgPackageData& package) {
            std::vector<float> flattened;
            for (int ch = 0; ch < package.channelCount; ++ch) {
                flattened.insert(flattened.end(), package.data[ch].begin(), package.data[ch].end());
            }
            callback(
                package.timeStamp,
                flattened.data(),
                static_cast<int>(flattened.size()),
                static_cast<int>(package.frequency),
                package.frequencyStd);
        });
    }

    MUDRA_API void set_parser_emg_resolution(ComputationManagerHandle computation, uint8_t bits) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->SetEmgResolutionBits(bits);
        }
    }

    MUDRA_API void set_parser_emg_channel_count(ComputationManagerHandle computation, uint8_t channels) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->SetEmgChannelCount(channels);
        }
    }

    MUDRA_API void set_parser_ppg_channel_count(ComputationManagerHandle computation, uint8_t channels) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->SetPpgChannelCount(channels);
        }
    }

    MUDRA_API void set_parser_imu_h_ranges(ComputationManagerHandle computation, uint8_t accel_range_g, uint16_t gyro_range_dps) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->SetImuHRanges(accel_range_g, gyro_range_dps);
        }
    }

    MUDRA_API void set_parser_imu_f_ranges(ComputationManagerHandle computation, uint8_t accel_range_g, uint16_t gyro_range_dps) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->SetImuFRanges(accel_range_g, gyro_range_dps);
        }
    }

    MUDRA_API void reset_packet_loss_stats(ComputationManagerHandle computation, int dataType) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->ResetPacketLossStats((FirmwareDataType)dataType);
        }
    }

    MUDRA_API void get_packet_loss_stats(ComputationManagerHandle computation, int dataType, uint64_t* samplesSeen, uint64_t* samplesLost) {
        if (computation && samplesSeen && samplesLost) {
            static_cast<ComputationManager*>(computation)->GetPacketLossStats((FirmwareDataType)dataType, *samplesSeen, *samplesLost);
        }
    }

    MUDRA_API ComputationManagerHandle create_computation() {
        try {
            return new ComputationManager(logger);
        }
        catch (const std::exception& e) {
            return nullptr;
        }
    }

    MUDRA_API void delete_computation(ComputationManagerHandle computation) {
        if (computation) {
            delete static_cast<ComputationManager*>(computation);
        }
    }

    MUDRA_API void enable_recording(ComputationManagerHandle computation) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->EnableRecording();
        }
    }

    MUDRA_API void disable_recording(ComputationManagerHandle computation) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->DisableRecording();
        }
    }

    MUDRA_API bool start_recording(ComputationManagerHandle computation, const Mudra::Computation::RecordingDataType* recordingTypes, int recordingTypesCount, int recordingMaxTime) {
        if (computation) {
            std::vector<RecordingDataType> recordingTypesVec(recordingTypes, recordingTypes + recordingTypesCount);
            return static_cast<ComputationManager*>(computation)->StartRecording(recordingTypesVec, recordingMaxTime);
        }
        return false;
    }

    MUDRA_API void record_emg_Fusion(ComputationManagerHandle computation, const char* data_tab, const float data) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->RecordEMGFusion(data_tab, data);
        }
    }

    MUDRA_API void add_video(ComputationManagerHandle computation, const char* key, const char* videoPath) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->AddVideo(key, videoPath);
        }
    }

    MUDRA_API void handle_data(ComputationManagerHandle computation, const uint8_t* data, size_t length) {
        if (computation) {
            std::vector<Byte> receivedData(data, data + length);
            static_cast<ComputationManager*>(computation)->HandleData(receivedData);
        }
    }

    MUDRA_API void stop_recording(ComputationManagerHandle computation) {
        if (computation) {
            static_cast<ComputationManager*>(computation)->StopRecording();
        }
    }

    MUDRA_API bool is_recording_enabled(ComputationManagerHandle computation) {
        if (computation) {
            return static_cast<ComputationManager*>(computation)->IsRecordingEnabled();
        }
        return false;
    }

    MUDRA_API void record_event(ComputationManagerHandle computation, int eventType, const char* eventName) {
        if (computation) {
            return static_cast<ComputationManager*>(computation)->RecordEvent((Mudra::Computation::EventType)eventType, eventName);
        }
    }

    MUDRA_API const char* get_json_recording(ComputationManagerHandle computation) {
        if (computation) {
            static std::string json;
            json = static_cast<ComputationManager*>(computation)->GetJsonRecording();
            return json.c_str();
        }
        return nullptr;
    }

    MUDRA_API void* fill_json_buffer(ComputationManagerHandle computation) {
        size_t buffer_size = static_cast<ComputationManager*>(computation)->GetRecordingSize();
        void* buffer = malloc(buffer_size);
        if (!computation || !buffer) {
            return 0;
        }

        std::string json_data = static_cast<ComputationManager*>(computation)->GetJsonRecording();
        size_t data_size = json_data.size();
        size_t copy_size = (std::min)(data_size, buffer_size - 1);

        memcpy(buffer, json_data.c_str(), copy_size);

        static_cast<char*>(buffer)[copy_size] = '\0';

        return buffer;
    }

    MUDRA_API void free_shared_buffer(void* buffer) {
        if (buffer) {
            free(buffer);
        }
    }

    MUDRA_API void save_recording(ComputationManagerHandle computation)
    {
        if (!computation) {
            return;
        }

        ComputationManager* manager = static_cast<ComputationManager*>(computation);

        manager->SaveRecording();
    }
}
