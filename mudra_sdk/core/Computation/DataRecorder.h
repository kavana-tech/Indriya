#pragma once

#include <memory>
#include <vector>
#include <map>
#include <set>

#include "Timer.h"
#include "CommonTypes.h"
#include "json11.hpp"

namespace Mudra::Computation
{
    class Logger;

    class DataRecorder {
        std::set<RecordingDataType> m_recordingDataTypes;

        struct Event {
            std::string name;
            double timeStamp;
        };
        map<EventType, std::vector<Event>> m_events;
        std::shared_ptr<Logger> m_logger;

        bool m_isEnabled;
        std::vector<BufferType> m_buffer;

        map<std::string, BufferType> m_emg_fusion_data;

        json11::Json m_root_json;

        map<std::string, std::string > m_videos;

        Timer m_timer;

        int m_recordingMaxTime;

        void ClearBuffer();

        void RecordAppTimeStampType(RecordingDataType type);

        void RecordSamples(const BufferType& samples, RecordingDataType type);
        void RecordRawTimeStamp(uint64_t timeStamp, RecordingDataType type);

        void RecordImuType(ImuPackageData& data, RecordingDataType acc1, RecordingDataType acc2, RecordingDataType acc3, RecordingDataType accTS,
                            RecordingDataType gyro1, RecordingDataType gyro2, RecordingDataType gyro3, RecordingDataType gyrTS);

        void AddEventsToJson(json11::Json::object& data_tab, EventType eventType, const std::string& key);

    public:
        DataRecorder(std::shared_ptr<Logger> logger);
        ~DataRecorder();

        void Enable();
        void Disable();
        bool StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime);
        bool StopRecording();
        std::string GetJsonRecording() const;
        void SaveRecording();
        void RecordFSR(int data);
        void RecordEvent(EventType eventType, const std::string& eventName);
        void AddVideo(const std::string& key, const std::string& videoPath);
        long GetRecordingSize() const { return (GetJsonRecording().length() + 1); }

        void RecordEMGFusion(const std::string& data_tab, float data);

        void RecordEMG(EmgPackageData& data);
        void RecordImuH(ImuPackageData& data);
        void RecordImuF(ImuPackageData& data);
        void RecordPPG(PpgPackageData& data);

        bool IsEnabled() const {return m_isEnabled;}
        bool IsDataNeeded(FirmwareDataType dataType);

        bool IsRecordingType(RecordingDataType recordingType);

        static const int INFINITE_TIME = 0;
    };

}
