#include <vector>
#include <cstring>

#include "Parser.h"

using namespace Mudra::Computation;
using namespace std;

template <class T>
T Parser::Bytes2Type(const Byte* b)
{
    T value{};
    memcpy(&value, b, sizeof(T));
    return value;
}

int16_t Parser::ReadI16LE(const Byte* b)
{
    return static_cast<int16_t>(b[0] | (b[1] << 8));
}

int32_t Parser::ReadI24LE(const Byte* b)
{
    int32_t v = b[0] | (b[1] << 8) | (b[2] << 16);
    if (v & 0x800000) {
        v |= ~0xFFFFFF;
    }
    return v;
}

Parser::Parser(shared_ptr<Logger> logger) :
    m_logger(logger),
    m_emgResolutionBits(16),
    m_emgChannelCount(3),
    m_ppgChannelCount(2),
    m_imuHAccRangeG(IMU_ACC_RANGE_G_DEFAULT),
    m_imuHGyrRangeDps(IMU_GYR_RANGE_DPS_DEFAULT),
    m_imuFAccRangeG(IMU_ACC_RANGE_G_DEFAULT),
    m_imuFGyrRangeDps(IMU_GYR_RANGE_DPS_DEFAULT)
{
    m_signalAnalyzers[FirmwareDataType::EMG] = make_shared<SignalAnalyzer>(FirmwareDataType::EMG, logger);
    m_signalAnalyzers[FirmwareDataType::IMU_H] = make_shared<SignalAnalyzer>(FirmwareDataType::IMU_H, logger);
    m_signalAnalyzers[FirmwareDataType::IMU_F] = make_shared<SignalAnalyzer>(FirmwareDataType::IMU_F, logger);
    m_signalAnalyzers[FirmwareDataType::PPG] = make_shared<SignalAnalyzer>(FirmwareDataType::PPG, logger);

    m_packetLossStats[FirmwareDataType::EMG] = PacketLossStats();
    m_packetLossStats[FirmwareDataType::IMU_H] = PacketLossStats();
    m_packetLossStats[FirmwareDataType::IMU_F] = PacketLossStats();
    m_packetLossStats[FirmwareDataType::PPG] = PacketLossStats();
}

Parser::~Parser()
{
}

void Parser::AddBytesToQueue(std::deque<Byte>& queue, const vector<Byte>& receivedData)
{
    for (const auto& b : receivedData) {
        queue.push_back(b);
    }
}

bool Parser::PeekSection(uint8_t& id, uint16_t& payloadLen) const
{
    if (m_bytesQueue.size() < DATA_SECTION_HEADER_SIZE) {
        return false;
    }
    id = m_bytesQueue[0];
    payloadLen = static_cast<uint16_t>(m_bytesQueue[1] | (m_bytesQueue[2] << 8));
    return true;
}

bool Parser::ConsumeSection(uint8_t& id, std::vector<Byte>& payload, uint64_t& timestamp)
{
    uint16_t payloadLen = 0;
    if (!PeekSection(id, payloadLen)) {
        return false;
    }

    const size_t sectionSize = DATA_SECTION_OVERHEAD + payloadLen;
    if (m_bytesQueue.size() < sectionSize) {
        return false;
    }

    m_bytesQueue.pop_front(); // id
    m_bytesQueue.pop_front(); // len lo
    m_bytesQueue.pop_front(); // len hi

    payload.clear();
    payload.reserve(payloadLen);
    for (uint16_t i = 0; i < payloadLen; ++i) {
        payload.push_back(m_bytesQueue.front());
        m_bytesQueue.pop_front();
    }

    Byte tsBytes[TIMESTAMP_SIZE];
    for (unsigned i = 0; i < TIMESTAMP_SIZE; ++i) {
        tsBytes[i] = m_bytesQueue.front();
        m_bytesQueue.pop_front();
    }
    timestamp = Bytes2Type<uint64_t>(tsBytes);
    return true;
}

unsigned int Parser::EmgSampleSize() const
{
    const unsigned int sampleWidth = (m_emgResolutionBits == 24) ? SAMPLE_SIZE_24_BIT : SAMPLE_SIZE_16_BIT;
    return m_emgChannelCount * sampleWidth;
}

unsigned int Parser::PpgSampleSize() const
{
    const unsigned int ch = (m_ppgChannelCount >= 1 && m_ppgChannelCount <= 4)
        ? m_ppgChannelCount
        : PPG_CHANNELS_2;
    return ch * SAMPLE_SIZE_24_BIT;
}

void Parser::SetEmgResolutionBits(uint8_t bits)
{
    if (bits != 16 && bits != 24) {
        ErrorMessage(m_logger) << "SetEmgResolutionBits invalid bits=" << static_cast<int>(bits) << endl;
        return;
    }
    if (bits == m_emgResolutionBits) {
        return;
    }
    m_emgResolutionBits = bits;
    Clear();
}

void Parser::SetEmgChannelCount(uint8_t channels)
{
    if (channels < 1 || channels > 8) {
        ErrorMessage(m_logger) << "SetEmgChannelCount invalid channels=" << static_cast<int>(channels) << endl;
        return;
    }
    if (channels == m_emgChannelCount) {
        return;
    }
    m_emgChannelCount = channels;
    Clear();
}

void Parser::SetPpgChannelCount(uint8_t channels)
{
    if (channels < 1 || channels > 4) {
        ErrorMessage(m_logger) << "SetPpgChannelCount invalid channels=" << static_cast<int>(channels) << endl;
        return;
    }
    if (channels == m_ppgChannelCount) {
        return;
    }
    m_ppgChannelCount = channels;
    Clear();
}

void Parser::ResetPacketLossStats(FirmwareDataType dataType)
{
    m_packetLossStats[dataType].Reset();
}

void Parser::GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const
{
    auto it = m_packetLossStats.find(dataType);
    if (it != m_packetLossStats.end()) {
        samplesSeen = it->second.samplesSeen;
        samplesLost = it->second.samplesLost;
    }
    else {
        samplesSeen = 0;
        samplesLost = 0;
    }
}

void Parser::SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps)
{
    if (accelRangeG == 0 || gyroRangeDps == 0) {
        ErrorMessage(m_logger) << "SetImuHRanges invalid acc=" << static_cast<int>(accelRangeG)
            << " gyr=" << gyroRangeDps << endl;
        return;
    }
    m_imuHAccRangeG = accelRangeG;
    m_imuHGyrRangeDps = gyroRangeDps;
}

void Parser::SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps)
{
    if (accelRangeG == 0 || gyroRangeDps == 0) {
        ErrorMessage(m_logger) << "SetImuFRanges invalid acc=" << static_cast<int>(accelRangeG)
            << " gyr=" << gyroRangeDps << endl;
        return;
    }
    m_imuFAccRangeG = accelRangeG;
    m_imuFGyrRangeDps = gyroRangeDps;
}

void Parser::HandleEmgSection(const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages)
{
    const unsigned int sampleSize = EmgSampleSize();
    if (payload.empty() || payload.size() % sampleSize != 0) {
        ErrorMessage(m_logger) << "Invalid EMG payload length " << payload.size()
            << " for " << static_cast<int>(m_emgResolutionBits) << "-bit sample size " << sampleSize << endl;
        return;
    }

    const float scale = 1.0f / ((m_emgResolutionBits == 24) ? EMG_RES_MAX_24 : EMG_RES_MAX_16);
    const unsigned int sampleWidth = (m_emgResolutionBits == 24) ? SAMPLE_SIZE_24_BIT : SAMPLE_SIZE_16_BIT;

    auto* package = new EmgPackageData();
    package->timeStamp = timestamp;
    package->channelCount = static_cast<int>(m_emgChannelCount);

    const size_t sampleCount = payload.size() / sampleSize;
    for (size_t s = 0; s < sampleCount; ++s) {
        const Byte* sample = payload.data() + s * sampleSize;
        for (unsigned ch = 0; ch < m_emgChannelCount; ++ch) {
            int32_t rawInt = (sampleWidth == SAMPLE_SIZE_16_BIT)
                ? ReadI16LE(sample + ch * SAMPLE_SIZE_16_BIT)
                : ReadI24LE(sample + ch * SAMPLE_SIZE_24_BIT);
            if (ch == 0) {
                m_packetLossStats[FirmwareDataType::EMG].Feed(rawInt);
            }
            package->data[ch].push_back(static_cast<float>(rawInt) * scale);
        }
    }

    m_signalAnalyzers[FirmwareDataType::EMG]->compute(*package);
    packages.push_back(package);
}

void Parser::HandleImuSection(PackageType type, FirmwareDataType dataType, const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages)
{
    if (payload.empty() || payload.size() % IMU_SAMPLE_SIZE != 0) {
        ErrorMessage(m_logger) << "Invalid IMU payload length " << payload.size() << endl;
        return;
    }

    const uint8_t accG = (type == PackageType::ImuH) ? m_imuHAccRangeG : m_imuFAccRangeG;
    const uint16_t gyrDps = (type == PackageType::ImuH) ? m_imuHGyrRangeDps : m_imuFGyrRangeDps;
    const float accScale = static_cast<float>(accG) / IMU_RAW_PEAK;
    const float gyrScale = static_cast<float>(gyrDps) / IMU_RAW_PEAK;

    auto* package = new ImuPackageData(type);
    package->timeStamp = timestamp;

    const size_t sampleCount = payload.size() / IMU_SAMPLE_SIZE;
    for (size_t s = 0; s < sampleCount; ++s) {
        const Byte* sample = payload.data() + s * IMU_SAMPLE_SIZE;
        for (unsigned axis = 0; axis < IMU_AXES; ++axis) {
            int32_t rawInt = ReadI16LE(sample + axis * SAMPLE_SIZE_16_BIT);
            if (axis == 0) {
                m_packetLossStats[dataType].Feed(rawInt);
            }
            const float scale = (axis < 3) ? accScale : gyrScale;
            package->data[axis].push_back(static_cast<float>(rawInt) * scale);
        }
    }

    m_signalAnalyzers[dataType]->compute(*package);
    packages.push_back(package);
}

void Parser::HandlePpgSection(const std::vector<Byte>& payload, uint64_t timestamp, vector<PackageData*>& packages)
{
    const unsigned int sampleSize = PpgSampleSize();
    if (payload.empty() || payload.size() % sampleSize != 0) {
        ErrorMessage(m_logger) << "Invalid PPG payload length " << payload.size()
            << " for " << static_cast<int>(m_ppgChannelCount) << "ch sample size " << sampleSize << endl;
        return;
    }

    auto* package = new PpgPackageData();
    package->timeStamp = timestamp;
    package->channelCount = static_cast<int>(sampleSize / SAMPLE_SIZE_24_BIT);

    const size_t sampleCount = payload.size() / sampleSize;
    for (size_t s = 0; s < sampleCount; ++s) {
        const Byte* sample = payload.data() + s * sampleSize;
        for (int ch = 0; ch < package->channelCount; ++ch) {
            int32_t rawInt = ReadI24LE(sample + ch * SAMPLE_SIZE_24_BIT);
            if (ch == 0) {
                m_packetLossStats[FirmwareDataType::PPG].Feed(rawInt);
            }
            package->data[ch].push_back(static_cast<float>(rawInt) * PPG_UV_PER_COUNT);
        }
    }

    m_signalAnalyzers[FirmwareDataType::PPG]->compute(*package);
    packages.push_back(package);
}

void Parser::HandleData(const vector<Byte>& receivedData, vector<PackageData*>& packages)
{
    AddBytesToQueue(m_bytesQueue, receivedData);

    while (!m_bytesQueue.empty()) {
        uint8_t id = 0;
        uint16_t payloadLen = 0;
        if (!PeekSection(id, payloadLen)) {
            return;
        }

        const size_t sectionSize = DATA_SECTION_OVERHEAD + payloadLen;
        if (m_bytesQueue.size() < sectionSize) {
            return;
        }

        std::vector<Byte> payload;
        uint64_t timestamp = 0;
        if (!ConsumeSection(id, payload, timestamp)) {
            return;
        }

        switch (id) {
        case DATA_HEADER_EMG:
            HandleEmgSection(payload, timestamp, packages);
            break;
        case DATA_HEADER_IMU_H:
            HandleImuSection(PackageType::ImuH, FirmwareDataType::IMU_H, payload, timestamp, packages);
            break;
        case DATA_HEADER_IMU_F:
            HandleImuSection(PackageType::ImuF, FirmwareDataType::IMU_F, payload, timestamp, packages);
            break;
        case DATA_HEADER_PPG:
            HandlePpgSection(payload, timestamp, packages);
            break;
        default:
            ErrorMessage(m_logger) << "HandleData unknown section id 0x" << hex << static_cast<int>(id) << dec << endl;
            Clear();
            return;
        }
    }
}

void Parser::Clear()
{
    m_bytesQueue.clear();
}
