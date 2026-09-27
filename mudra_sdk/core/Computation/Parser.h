#pragma once

#include "CommonTypes.h"
#include "Logging.h"
#include "Constants.h"
#include "SignalAnalyzer.h"

#include <deque>
#include <vector>
#include <memory>
#include <map>

namespace Mudra::Computation
{
    class Parser
    {
        std::deque<Byte> m_bytesQueue;
        shared_ptr<Logger> m_logger;
        std::map<FirmwareDataType, shared_ptr<SignalAnalyzer>> m_signalAnalyzers;
        std::map<FirmwareDataType, PacketLossStats> m_packetLossStats;

        /* Host-known sensor config (from STATUS / setters). Required for correct
         * EMG/PPG stride — payload length alone is ambiguous (see ble.md). */
        uint8_t m_emgResolutionBits;   /* 16 or 24; boot default 16 */
        uint8_t m_emgChannelCount;     /* 3 (Pro) or 8 (Ultimate); boot default 3 */
        uint8_t m_ppgChannelCount;     /* 2 or 4 typically; boot default 2 */
        uint8_t m_imuHAccRangeG;       /* ±g full-scale */
        uint16_t m_imuHGyrRangeDps;
        uint8_t m_imuFAccRangeG;
        uint16_t m_imuFGyrRangeDps;

        void AddBytesToQueue(std::deque<Byte>& queue, const vector<Byte>& receivedData);
        bool PeekSection(uint8_t& id, uint16_t& payloadLen) const;
        bool ConsumeSection(uint8_t& id, std::vector<Byte>& payload, uint64_t& timestamp);

        unsigned int EmgSampleSize() const;
        unsigned int PpgSampleSize() const;

        void HandleEmgSection(const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages);
        void HandleImuSection(PackageType type, FirmwareDataType dataType, const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages);
        void HandlePpgSection(const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages);

        static int16_t ReadI16LE(const Byte* b);
        static int32_t ReadI24LE(const Byte* b);
        template <class T>
        static T Bytes2Type(const Byte* b);

    public:
        Parser(shared_ptr<Logger> logger);
        ~Parser();

        void Clear();
        void HandleData(const vector<Byte>& receivedData, vector<PackageData*>& packages);

        /* Update parse/scale config. Clears the byte queue when EMG/PPG stride changes. */
        void SetEmgResolutionBits(uint8_t bits);
        void SetEmgChannelCount(uint8_t channels);
        void SetPpgChannelCount(uint8_t channels);
        void SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);
        void SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);

        /* Packet-loss test-mode counters — see PacketLossStats (CommonTypes.h). */
        void ResetPacketLossStats(FirmwareDataType dataType);
        void GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const;
    };
}
