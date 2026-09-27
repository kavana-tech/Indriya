
#include "DataRecorder.h"
#include "Logging.h"
#include "ComputationManager.h"
#include "CommonTypes.h"

using namespace Mudra::Computation;
using namespace json11;

DataRecorder::DataRecorder(shared_ptr<Logger> logger)
: m_logger(logger),
m_timer("Recording Timer", logger),
m_isEnabled(true)
{
    for (int i = 0; i < (int)RecordingDataType::NumOfRecordingTypes; i++)
        m_buffer.push_back(BufferType());
}

DataRecorder::~DataRecorder()
{
}

void DataRecorder::ClearBuffer()
{
    for (int i = 0; i < (int)RecordingDataType::NumOfRecordingTypes; i++)
        m_buffer[i].clear();
}

void Mudra::Computation::DataRecorder::Enable()
{
    m_isEnabled = true;
    InfoMessage(m_logger)<<"DataRecorder Turned On"<<endl;
}

void Mudra::Computation::DataRecorder::Disable()
{
    m_isEnabled = false;
    InfoMessage(m_logger) << "DataRecorder Turned Off" << endl;
}

bool DataRecorder::StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime)
{
    m_timer.Start();
    m_recordingMaxTime = recordingMaxTime;
    ErrorMessage(m_logger) << "Start recording";
    if (!m_isEnabled) {
        ErrorMessage(m_logger) << "Recordong is disabled";
        return false;
    }

    if (m_recordingDataTypes.size() !=0) {
        return false;
    }

    m_root_json = Json::object();

    m_events[EventType::ButtonEvent].clear();
    m_videos.clear();
    m_emg_fusion_data.clear();
    ClearBuffer();
    for (const auto& recordingType : recordingTypes) {
        m_recordingDataTypes.insert(recordingType);
    }

    return true;
}

bool DataRecorder::StopRecording()
{
    ErrorMessage(m_logger) << "StopRecording" ;
    if (!m_isEnabled) {
        ErrorMessage(m_logger) << "Recording is disabled";
        return false;
    }

    RecordAppTimeStampType(RecordingDataType::EndAppTS);

    m_recordingDataTypes.clear();
    SaveRecording();
    
    return true;
}

string DataRecorder::GetJsonRecording() const
{
    return Json(m_root_json).dump();
}

void DataRecorder::RecordFSR(int data)
{
    m_buffer[RecordingDataType::FSR].push_back(data);
}


void DataRecorder::SaveRecording()
{
    Json::object data_tab;
    Json::object data_tab_emg;
    Json::object data_tab_acc;
    Json::object data_tab_gyr;
    Json::object data_tab_acc_f;
    Json::object data_tab_gyr_f;
    Json::object data_tab_ppg;
    Json::object emg_fusion_data_tab;

    for (int i = 0; i < NumOfRecordingTypes; i++) {
        if (m_buffer[i].empty()) continue;

        if (i == RecordingDataType::Button ||
            i == RecordingDataType::FSR ||
            i == RecordingDataType::EndAppTS) {
            data_tab[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::Emg1 || i == RecordingDataType::Emg2 ||
            i == RecordingDataType::Emg3 || i == RecordingDataType::EmgTS) {
            data_tab_emg[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::Acc1 || i == RecordingDataType::Acc2 ||
            i == RecordingDataType::Acc3 || i == RecordingDataType::AccTS) {
            data_tab_acc[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::Gyro1 || i == RecordingDataType::Gyro2 ||
            i == RecordingDataType::Gyro3 || i == RecordingDataType::GyrTS) {
            data_tab_gyr[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::AccF1 || i == RecordingDataType::AccF2 ||
            i == RecordingDataType::AccF3 || i == RecordingDataType::AccFTS) {
            data_tab_acc_f[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::GyroF1 || i == RecordingDataType::GyroF2 ||
            i == RecordingDataType::GyroF3 || i == RecordingDataType::GyrFTS) {
            data_tab_gyr_f[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }

        if (i == RecordingDataType::Ppg1 || i == RecordingDataType::Ppg2 ||
            i == RecordingDataType::Ppg3 || i == RecordingDataType::Ppg4 ||
            i == RecordingDataType::PpgTS) {
            data_tab_ppg[ComputationManager::ToString(RecordingDataType(i))] = Json(m_buffer[i]);
        }
    }

    if (data_tab_emg.size() != 0) {
        data_tab["emg"] = data_tab_emg;
    }
    if (data_tab_acc.size() != 0) {
        data_tab["acc"] = data_tab_acc;
    }
    if (data_tab_gyr.size() != 0) {
        data_tab["gyro"] = data_tab_gyr;
    }
    if (data_tab_acc_f.size() != 0) {
        data_tab["acc_f"] = data_tab_acc_f;
    }
    if (data_tab_gyr_f.size() != 0) {
        data_tab["gyro_f"] = data_tab_gyr_f;
    }
    if (data_tab_ppg.size() != 0) {
        data_tab["ppg"] = data_tab_ppg;
    }

    if (m_emg_fusion_data.begin() != m_emg_fusion_data.end()) {
        for (auto it = m_emg_fusion_data.begin(); it != m_emg_fusion_data.end(); ++it)
        {
            emg_fusion_data_tab[it->first] = Json(it->second);
        }
        data_tab["emg_fusion"] = emg_fusion_data_tab;
    }
    
    AddEventsToJson(data_tab, EventType::ButtonEvent, "button");

    Json::object root_obj = m_root_json.object_items();
    for (const auto& kv : data_tab) {
        root_obj[kv.first] = kv.second;
    }
    m_root_json = Json(root_obj);
}

void DataRecorder::AddEventsToJson(Json::object& data_tab, EventType eventType, const std::string& key)
{
    if (!m_events[eventType].empty()) {
        Json::array eventsArray;
        for (const auto& event : m_events[eventType]) {
            Json::object eventObj;
            eventObj["name"] = event.name;
            eventObj["timeStamp"] = event.timeStamp;
            eventsArray.push_back(eventObj);
        }
        data_tab[key] = eventsArray;
    }
}

void Mudra::Computation::DataRecorder::RecordEMGFusion(const std::string& data_tab, float data)
{
    m_emg_fusion_data[data_tab].push_back(data);
}

void DataRecorder::RecordSamples(const BufferType& samples, RecordingDataType type)
{
    if (!IsRecordingType(type)) {
        return;
    }

    m_buffer[type].insert(m_buffer[type].end(), samples.begin(), samples.end());
}

void DataRecorder::RecordRawTimeStamp(uint64_t timeStamp, RecordingDataType type)
{
    if (!IsRecordingType(type)) {
        return;
    }

    m_buffer[type].push_back(static_cast<float>(timeStamp));
}

void DataRecorder::RecordEMG(EmgPackageData& data)
{
    RecordSamples(data.data[0], RecordingDataType::Emg1);
    RecordSamples(data.data[1], RecordingDataType::Emg2);
    RecordSamples(data.data[2], RecordingDataType::Emg3);
    RecordRawTimeStamp(data.timeStamp, RecordingDataType::EmgTS);
}

void DataRecorder::RecordImuType(ImuPackageData& data, RecordingDataType acc1, RecordingDataType acc2, RecordingDataType acc3, RecordingDataType accTS,
                                  RecordingDataType gyro1, RecordingDataType gyro2, RecordingDataType gyro3, RecordingDataType gyrTS)
{
    RecordSamples(data.data[0], acc1);
    RecordSamples(data.data[1], acc2);
    RecordSamples(data.data[2], acc3);
    RecordRawTimeStamp(data.timeStamp, accTS);

    RecordSamples(data.data[3], gyro1);
    RecordSamples(data.data[4], gyro2);
    RecordSamples(data.data[5], gyro3);
    RecordRawTimeStamp(data.timeStamp, gyrTS);
}

void DataRecorder::RecordImuH(ImuPackageData& data)
{
    RecordImuType(data,
        RecordingDataType::Acc1, RecordingDataType::Acc2, RecordingDataType::Acc3, RecordingDataType::AccTS,
        RecordingDataType::Gyro1, RecordingDataType::Gyro2, RecordingDataType::Gyro3, RecordingDataType::GyrTS);
}

void DataRecorder::RecordImuF(ImuPackageData& data)
{
    RecordImuType(data,
        RecordingDataType::AccF1, RecordingDataType::AccF2, RecordingDataType::AccF3, RecordingDataType::AccFTS,
        RecordingDataType::GyroF1, RecordingDataType::GyroF2, RecordingDataType::GyroF3, RecordingDataType::GyrFTS);
}

void DataRecorder::RecordPPG(PpgPackageData& data)
{
    static const RecordingDataType channelTypes[4] = {
        RecordingDataType::Ppg1, RecordingDataType::Ppg2,
        RecordingDataType::Ppg3, RecordingDataType::Ppg4
    };

    for (int ch = 0; ch < data.channelCount && ch < 4; ch++) {
        RecordSamples(data.data[ch], channelTypes[ch]);
    }
    RecordRawTimeStamp(data.timeStamp, RecordingDataType::PpgTS);
}

void DataRecorder::RecordAppTimeStampType(RecordingDataType type)
{
    if (!IsRecordingType(type)) {
        return;
    }
    
    m_buffer[type].push_back(m_timer.GetMillisElapsedTime());
}

void DataRecorder::RecordEvent(EventType eventType, const std::string& eventName)
{
    if (!m_isEnabled || m_recordingDataTypes.size() == 0) {
        return;
    }
    
    double currentTime = m_timer.GetElapsedTime();
    m_events[eventType].push_back({eventName, currentTime});
    
    InfoMessage(m_logger) << "Event recorded: " << eventName << " at time " << currentTime << " seconds" << endl;
}

void DataRecorder::AddVideo(const std::string& key, const std::string& videoPath)
{
    m_videos[key] = videoPath;
    Json::object root_obj = m_root_json.object_items();
    root_obj["videos"] = m_videos;
    m_root_json = Json(root_obj);
}

bool Mudra::Computation::DataRecorder::IsDataNeeded(FirmwareDataType dataType)
{
    if (!m_isEnabled) {
        return false;
    }

    switch (dataType) {
    case FirmwareDataType::EMG:
        return IsRecordingType(RecordingDataType::Emg1) ||
               IsRecordingType(RecordingDataType::Emg2) ||
               IsRecordingType(RecordingDataType::Emg3) ||
               IsRecordingType(RecordingDataType::EmgTS);

    case FirmwareDataType::IMU_H:
        return IsRecordingType(RecordingDataType::Acc1) ||
               IsRecordingType(RecordingDataType::Acc2) ||
               IsRecordingType(RecordingDataType::Acc3) ||
               IsRecordingType(RecordingDataType::AccTS) ||
               IsRecordingType(RecordingDataType::Gyro1) ||
               IsRecordingType(RecordingDataType::Gyro2) ||
               IsRecordingType(RecordingDataType::Gyro3) ||
               IsRecordingType(RecordingDataType::GyrTS);

    case FirmwareDataType::IMU_F:
        return IsRecordingType(RecordingDataType::AccF1) ||
               IsRecordingType(RecordingDataType::AccF2) ||
               IsRecordingType(RecordingDataType::AccF3) ||
               IsRecordingType(RecordingDataType::AccFTS) ||
               IsRecordingType(RecordingDataType::GyroF1) ||
               IsRecordingType(RecordingDataType::GyroF2) ||
               IsRecordingType(RecordingDataType::GyroF3) ||
               IsRecordingType(RecordingDataType::GyrFTS);

    case FirmwareDataType::PPG:
        return IsRecordingType(RecordingDataType::Ppg1) ||
               IsRecordingType(RecordingDataType::Ppg2) ||
               IsRecordingType(RecordingDataType::Ppg3) ||
               IsRecordingType(RecordingDataType::Ppg4) ||
               IsRecordingType(RecordingDataType::PpgTS);

    default:
        return false;
    }
}

bool Mudra::Computation::DataRecorder::IsRecordingType(RecordingDataType recordingType)
{
    return (m_recordingMaxTime == INFINITE_TIME || m_timer.GetElapsedTime() <= m_recordingMaxTime) && m_recordingDataTypes.find(recordingType) != m_recordingDataTypes.end();
}
