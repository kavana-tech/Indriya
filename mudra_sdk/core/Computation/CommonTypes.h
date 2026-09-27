#pragma once

#include <vector>
#include <string>
#include <iostream>
#include <memory>
#include <functional>
#include <cstdint>

namespace Mudra::Computation
{
    typedef unsigned char Byte; //uint8_t

    typedef std::vector<float> BufferType;

    enum FirmwareDataType
    {
        EMG = 0,
        IMU_H = 1,
        IMU_F = 2,
        PPG = 3
    };

    enum class PackageType
    {
        None = -1,
        Emg = 0x10,
        ImuH = 0x20,
        ImuF = 0x30,
        Ppg = 0x40,
        Event = 30
    };

    /*
     * Decoded sensor package (one BLE/USB DATA section).
     * Wire layout: [id:1][len:2 LE][payload][ts:8 LE]  — see Constants.h.
     *
     * timeStamp     — last-sample ts_cyc (FLPR k_cycle_get_64, GRTC-backed, no rollover)
     * frequency     — packages/sec over the last ~1 s (not sample ODR)
     * frequencyStd  — stddev of recent package-rate history
     */
    class PackageData
    {
    public:

        PackageType type;
        uint64_t timeStamp;
        unsigned int frequency;
        float frequencyStd;
        
        PackageData(PackageType packageType) :  type(packageType), timeStamp(), frequency(), frequencyStd() {}
        virtual ~PackageData() = default;
    };

    struct EventPackageData  : public PackageData
    {
        std::string event;
        
        EventPackageData() :  PackageData(PackageType::Event) {}
    };

    /*
     * EMG (id 0x10) — scaled to ~[-1, 1] using STATUS resolution (emg_res_max).
     * Wire sample: N channels interleaved (N = channelCount; 3 on Pro, 8 on
     * Ultimate), int16 or int24 LE per channel; channelCount set from config.
     * data[ch][i] = sample i on channel ch (ch = 0..channelCount-1).
     */
    struct EmgPackageData : public PackageData
    {
        BufferType data[8];
        int channelCount;

        EmgPackageData() : PackageData(PackageType::Emg), channelCount(3) {}
    };

    /*
     * Hand IMU (id 0x20) / Finger IMU (id 0x30)
     * Wire: 6 × int16 LE — [ax, ay, az, gx, gy, gz]; scaled to g / dps via STATUS ranges.
     * data[axis][i] = sample i on axis (0=ax … 5=gz).
     */
    struct ImuPackageData : public PackageData
    {
        BufferType data[6];

        explicit ImuPackageData(PackageType packageType) : PackageData(packageType) {}
    };

    /*
     * PPG (id 0x40) — scaled to µV using AFE4950 count→µV factor.
     * Wire sample: N × int24 LE (N from STATUS channel_count); channelCount set from config.
     * data[ch][i] = sample i on channel ch (ch = 0..channelCount-1).
     */
    struct PpgPackageData : public PackageData
    {
        BufferType data[4];
        int channelCount;

        PpgPackageData() : PackageData(PackageType::Ppg), channelCount(2) {}
    };

    enum RecordingDataType
    {
        Button,
        FSR,
        EndAppTS,

        Emg1, Emg2, Emg3, EmgTS,

        // Hand IMU (PackageType::ImuH)
        Acc1, Acc2, Acc3, AccTS,
        Gyro1, Gyro2, Gyro3, GyrTS,

        // Finger IMU (PackageType::ImuF)
        AccF1, AccF2, AccF3, AccFTS,
        GyroF1, GyroF2, GyroF3, GyrFTS,

        Ppg1, Ppg2, Ppg3, Ppg4, PpgTS,

        NumOfRecordingTypes
    };

    /*
     * Packet-loss counter check, generic across EMG/IMU/PPG and independent
     * of any per-sensor physical-unit scale factor: it operates on the RAW
     * (pre-scale) channel-0 integer read straight off the wire, where the
     * firmware's counter test mode contract is exact — each real sample
     * increments it by precisely 1 — so "did the raw value increase by
     * exactly 1" needs no knowledge of resolution/range/ODR, and no notion
     * of which sensor or whether test mode is even active; it's simply fed
     * whatever raw channel-0 value shows up on every decode.
     */
    struct PacketLossStats
    {
        uint64_t samplesSeen = 0;
        uint64_t samplesLost = 0;
        bool     hasLast = false;
        int32_t  lastValue = 0;

        void Feed(int32_t rawValue)
        {
            if (hasLast) {
                int32_t diff = rawValue - lastValue;
                if (diff >= 1) {
                    samplesLost += static_cast<uint64_t>(diff - 1);
                }
                // diff <= 0: wrap/reorder/duplicate — not counted, same
                // blind spot any simple continuity check has.
            }
            lastValue = rawValue;
            hasLast = true;
            samplesSeen++;
        }

        void Reset()
        {
            samplesSeen = 0;
            samplesLost = 0;
            hasLast = false;
            lastValue = 0;
        }

        double LossPct() const
        {
            uint64_t total = samplesSeen + samplesLost;
            return total ? (100.0 * static_cast<double>(samplesLost) / static_cast<double>(total)) : 0.0;
        }
    };

    enum class EventType
    {
        ButtonEvent = 1
    };

    typedef std::function< void(const std::string &msg)>        OnLoggingMessageCallBackType;
    typedef std::function< void(EmgPackageData&)>               OnEmgPackageReadyCallbackType;
    typedef std::function< void(ImuPackageData&)>               OnImuPackageReadyCallbackType;
    typedef std::function< void(PpgPackageData&)>               OnPpgPackageReadyCallbackType;
}
