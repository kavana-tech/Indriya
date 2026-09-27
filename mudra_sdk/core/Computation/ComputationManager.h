#pragma once

#include <cstdint>
#include <memory>

#include "CommonTypes.h"
#include "Logging.h"

#ifdef _WINDOWS
#ifdef  MUDRAWINDOWSDESKTOP_EXPORTS
/*Enabled as "export" while compiling the dll project*/
#define DLLEXPORT __declspec(dllexport)
#else
/*Enabled as "import" in the Client side for using already created dll file*/
#define DLLEXPORT __declspec(dllimport)
#endif
#else
#define DLLEXPORT
#endif

namespace Mudra::Computation
{
    class ComputationManager
    {
        class impl;
        impl* m_impl;

    public:
        DLLEXPORT ComputationManager(shared_ptr<Logger> logger);
        DLLEXPORT ~ComputationManager();

        void DLLEXPORT HandleData(const vector<Byte>& data);

        /* Push sensor STATUS into the DATA parser (stride + physical scaling). */
        void DLLEXPORT SetEmgResolutionBits(uint8_t bits);
        void DLLEXPORT SetEmgChannelCount(uint8_t channels);
        void DLLEXPORT SetPpgChannelCount(uint8_t channels);
        void DLLEXPORT SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);
        void DLLEXPORT SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);

        /* Packet-loss test-mode counters — see PacketLossStats (CommonTypes.h). */
        void DLLEXPORT ResetPacketLossStats(FirmwareDataType dataType);
        void DLLEXPORT GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const;

        static string DLLEXPORT ToString(RecordingDataType h);

        void DLLEXPORT SetOnEmgPackageReadyCallBack(OnEmgPackageReadyCallbackType callback);
        void DLLEXPORT SetOnImuHPackageReadyCallBack(OnImuPackageReadyCallbackType callback);
        void DLLEXPORT SetOnImuFPackageReadyCallBack(OnImuPackageReadyCallbackType callback);
        void DLLEXPORT SetOnPpgPackageReadyCallBack(OnPpgPackageReadyCallbackType callback);
        bool DLLEXPORT IsDataNeeded(FirmwareDataType dataType) const;

        //Recording tool callbacks.
        void DLLEXPORT EnableRecording();
        void DLLEXPORT DisableRecording();
        bool DLLEXPORT IsRecordingEnabled();
        bool DLLEXPORT StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime);
        bool DLLEXPORT StopRecording();

        string DLLEXPORT GetJsonRecording();
        void DLLEXPORT SaveRecording();
        void DLLEXPORT RecordFSR(int data);
        long DLLEXPORT GetRecordingSize() const;
        void DLLEXPORT RecordEMGFusion(const std::string& data_tab, float data);
        void DLLEXPORT AddVideo(const std::string& key, const std::string& videoPath);
        void DLLEXPORT RecordEvent(EventType eventType, const std::string& eventName);
    };
}
