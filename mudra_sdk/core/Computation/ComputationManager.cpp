#include "ComputationManager.h"
#include "Parser.h"
#include "CommonTypes.h"
#include "DataRecorder.h"
#include "Logging.h"

#include <memory>
#include <mutex>

namespace Mudra
{
    namespace Computation
    {
        class ComputationManager::impl
        {
            unique_ptr<Parser> m_parser;
            shared_ptr<DataRecorder> m_dataRecorder;

            shared_ptr<Logger> m_logger;

            mutable std::recursive_mutex m_mutex;

            OnEmgPackageReadyCallbackType m_onEmgReady;
            OnImuPackageReadyCallbackType m_onImuHReady;
            OnImuPackageReadyCallbackType m_onImuFReady;
            OnPpgPackageReadyCallbackType m_onPpgReady;

            void HandlePackages(vector<PackageData*>& packages);

        public:
            impl(shared_ptr<Logger> logger);


            void HandleData(const vector<Byte>& recievedData);

            void SetEmgResolutionBits(uint8_t bits);
            void SetEmgChannelCount(uint8_t channels);
            void SetPpgChannelCount(uint8_t channels);
            void SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);
            void SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps);

            void ResetPacketLossStats(FirmwareDataType dataType);
            void GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const;

            void SetOnEmgPackageReadyCallBack(OnEmgPackageReadyCallbackType callback);
            void SetOnImuHPackageReadyCallBack(OnImuPackageReadyCallbackType callback);
            void SetOnImuFPackageReadyCallBack(OnImuPackageReadyCallbackType callback);
            void SetOnPpgPackageReadyCallBack(OnPpgPackageReadyCallbackType callback);
            bool IsDataNeeded(FirmwareDataType dataType) const;

            static string ToString(RecordingDataType type);

            //Recording tool callbacks.
            void EnableRecording();
            void DisableRecording();
            bool IsRecordingEnabled();
            bool StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime);
            bool StopRecording();
            string GetJsonRecording();
            void SaveRecording();
            void RecordFSR(int data);
            long GetRecordingSize() const;
            void RecordEMGFusion(const std::string& data_tab, float data);
            void RecordEvent(EventType eventType, const std::string& eventName);
            void AddVideo(const std::string& key, const std::string& videoPath);

        };

        ComputationManager::impl::impl(shared_ptr<Logger> logger) :
            m_logger(logger)
        {
            try
            {
                m_dataRecorder = make_shared<DataRecorder>(logger);

                m_parser = make_unique<Parser>(m_logger);

            }
            catch (const exception& e)
            {
                ErrorMessage(m_logger) << "Initialization Mudra error " << e.what();
            }
            catch (...)
            {
                ErrorMessage(m_logger) << "Initialization Mudra error ";
            }
        }

        void ComputationManager::impl::HandleData(const vector<Byte>& recievedData)
        {
            lock_guard<recursive_mutex> lck(m_mutex);


            try
            {
                vector<PackageData*> packages;

                m_parser->HandleData(recievedData, packages);

                HandlePackages(packages);
            }
            catch (const exception& e)
            {
                ErrorMessage(m_logger) << "Handle DATA Mudra error " << e.what();
            }
            catch (...)
            {
                ErrorMessage(m_logger) << "Handle DATA Mudra error ";
            }

        }

        void ComputationManager::impl::SetEmgResolutionBits(uint8_t bits)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->SetEmgResolutionBits(bits);
        }

        void ComputationManager::impl::SetEmgChannelCount(uint8_t channels)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->SetEmgChannelCount(channels);
        }

        void ComputationManager::impl::SetPpgChannelCount(uint8_t channels)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->SetPpgChannelCount(channels);
        }

        void ComputationManager::impl::SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->SetImuHRanges(accelRangeG, gyroRangeDps);
        }

        void ComputationManager::impl::SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->SetImuFRanges(accelRangeG, gyroRangeDps);
        }

        void ComputationManager::impl::ResetPacketLossStats(FirmwareDataType dataType)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->ResetPacketLossStats(dataType);
        }

        void ComputationManager::impl::GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_parser->GetPacketLossStats(dataType, samplesSeen, samplesLost);
        }

        void ComputationManager::impl::HandlePackages(vector<PackageData*>& packages)
        {
            for (auto& package : packages)
            {
                switch (package->type) {
                case PackageType::Emg:
                {
                    EmgPackageData& emgPackage = static_cast<EmgPackageData&>(*package);
                    if (m_onEmgReady) {
                        m_onEmgReady(emgPackage);
                    }
                    m_dataRecorder->RecordEMG(emgPackage);
                }
                break;
                case PackageType::ImuH:
                {
                    ImuPackageData& imuHPackage = static_cast<ImuPackageData&>(*package);
                    if (m_onImuHReady) {
                        m_onImuHReady(imuHPackage);
                    }
                    m_dataRecorder->RecordImuH(imuHPackage);
                }
                break;
                case PackageType::ImuF:
                {
                    ImuPackageData& imuFPackage = static_cast<ImuPackageData&>(*package);
                    if (m_onImuFReady) {
                        m_onImuFReady(imuFPackage);
                    }
                    m_dataRecorder->RecordImuF(imuFPackage);
                }
                break;
                case PackageType::Ppg:
                {
                    PpgPackageData& ppgPackage = static_cast<PpgPackageData&>(*package);
                    if (m_onPpgReady) {
                        m_onPpgReady(ppgPackage);
                    }
                    m_dataRecorder->RecordPPG(ppgPackage);
                }
                break;
                default:
                    break;
                }

                delete package;
            }
        }

        string ComputationManager::impl::ToString(RecordingDataType dataType)
        {
            switch (dataType) {
            case RecordingDataType::EmgTS:
            case RecordingDataType::AccTS:
            case RecordingDataType::GyrTS:
            case RecordingDataType::AccFTS:
            case RecordingDataType::GyrFTS:
            case RecordingDataType::PpgTS:
                return "ts";
            case RecordingDataType::Emg1:
            case RecordingDataType::Acc1:
            case RecordingDataType::Gyro1:
            case RecordingDataType::AccF1:
            case RecordingDataType::GyroF1:
            case RecordingDataType::Ppg1:
                return "1";
            case RecordingDataType::Emg2:
            case RecordingDataType::Acc2:
            case RecordingDataType::Gyro2:
            case RecordingDataType::AccF2:
            case RecordingDataType::GyroF2:
            case RecordingDataType::Ppg2:
                return "2";
            case RecordingDataType::Emg3:
            case RecordingDataType::Acc3:
            case RecordingDataType::Gyro3:
            case RecordingDataType::AccF3:
            case RecordingDataType::GyroF3:
            case RecordingDataType::Ppg3:
                return "3";
            case RecordingDataType::Ppg4:
                return "4";
            case RecordingDataType::EndAppTS:
                return "end_app_ts";
            case RecordingDataType::Button:
                return "button";
            case RecordingDataType::FSR:
                return "fsr";
            }

            return "none";
        }

        bool ComputationManager::impl::IsDataNeeded(FirmwareDataType dataType) const
        {
            if (m_dataRecorder->IsDataNeeded(dataType)) {
                return true;
            }

            switch (dataType) {
            case FirmwareDataType::EMG:
                return static_cast<bool>(m_onEmgReady);
            case FirmwareDataType::IMU_H:
                return static_cast<bool>(m_onImuHReady);
            case FirmwareDataType::IMU_F:
                return static_cast<bool>(m_onImuFReady);
            case FirmwareDataType::PPG:
                return static_cast<bool>(m_onPpgReady);
            default:
                return false;
            }
        }

        void ComputationManager::impl::SetOnEmgPackageReadyCallBack(OnEmgPackageReadyCallbackType callback)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_onEmgReady = callback;
        }

        void ComputationManager::impl::SetOnImuHPackageReadyCallBack(OnImuPackageReadyCallbackType callback)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_onImuHReady = callback;
        }

        void ComputationManager::impl::SetOnImuFPackageReadyCallBack(OnImuPackageReadyCallbackType callback)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_onImuFReady = callback;
        }

        void ComputationManager::impl::SetOnPpgPackageReadyCallBack(OnPpgPackageReadyCallbackType callback)
        {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_onPpgReady = callback;
        }

        bool ComputationManager::impl::IsRecordingEnabled() {
            lock_guard<recursive_mutex> lck(m_mutex);
            return m_dataRecorder->IsEnabled();
        }

        void ComputationManager::impl::EnableRecording() {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->Enable();
        }

        void ComputationManager::impl::DisableRecording() {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->Disable();
        }

        bool ComputationManager::impl::StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime) {
            lock_guard<recursive_mutex> lck(m_mutex);
            return m_dataRecorder->StartRecording(recordingTypes, recordingMaxTime);
        }

        bool ComputationManager::impl::StopRecording() {
            lock_guard<recursive_mutex> lck(m_mutex);
            return m_dataRecorder->StopRecording();
        }

        string ComputationManager::impl::GetJsonRecording() {
            lock_guard<recursive_mutex> lck(m_mutex);
            return m_dataRecorder->GetJsonRecording();
        }

        void ComputationManager::impl::SaveRecording() {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->SaveRecording();
        }

        void ComputationManager::impl::RecordFSR(int data) {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->RecordFSR(data);
        }

        void ComputationManager::impl::RecordEvent(EventType eventType, const std::string& eventName) {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->RecordEvent(eventType, eventName);
        }

        void ComputationManager::impl::AddVideo(const std::string& key, const std::string& videoPath) {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->AddVideo(key, videoPath);
        }

        void ComputationManager::impl::RecordEMGFusion(const std::string& data_tab, float data) {
            lock_guard<recursive_mutex> lck(m_mutex);
            m_dataRecorder->RecordEMGFusion(data_tab, data);
        }

        long ComputationManager::impl::GetRecordingSize() const {
            lock_guard<recursive_mutex> lck(m_mutex);
            return m_dataRecorder->GetRecordingSize();
        }

        ComputationManager::ComputationManager(shared_ptr<Logger> logger)
            :m_impl(new ComputationManager::impl(logger)) {
        }

        ComputationManager::~ComputationManager() { delete m_impl; }

        void ComputationManager::HandleData(const vector<Byte>& recievedData) { m_impl->HandleData(recievedData); }

        void ComputationManager::SetEmgResolutionBits(uint8_t bits) { m_impl->SetEmgResolutionBits(bits); }
        void ComputationManager::SetEmgChannelCount(uint8_t channels) { m_impl->SetEmgChannelCount(channels); }
        void ComputationManager::SetPpgChannelCount(uint8_t channels) { m_impl->SetPpgChannelCount(channels); }
        void ComputationManager::SetImuHRanges(uint8_t accelRangeG, uint16_t gyroRangeDps) { m_impl->SetImuHRanges(accelRangeG, gyroRangeDps); }
        void ComputationManager::SetImuFRanges(uint8_t accelRangeG, uint16_t gyroRangeDps) { m_impl->SetImuFRanges(accelRangeG, gyroRangeDps); }

        void ComputationManager::ResetPacketLossStats(FirmwareDataType dataType) { m_impl->ResetPacketLossStats(dataType); }
        void ComputationManager::GetPacketLossStats(FirmwareDataType dataType, uint64_t& samplesSeen, uint64_t& samplesLost) const { m_impl->GetPacketLossStats(dataType, samplesSeen, samplesLost); }

        string ComputationManager::ToString(RecordingDataType t) { return ComputationManager::impl::ToString(t); };


        bool ComputationManager::IsDataNeeded(FirmwareDataType dataType) const { return m_impl->IsDataNeeded(dataType); }
        void ComputationManager::SetOnEmgPackageReadyCallBack(OnEmgPackageReadyCallbackType callback) { m_impl->SetOnEmgPackageReadyCallBack(callback); }
        void ComputationManager::SetOnImuHPackageReadyCallBack(OnImuPackageReadyCallbackType callback) { m_impl->SetOnImuHPackageReadyCallBack(callback); }
        void ComputationManager::SetOnImuFPackageReadyCallBack(OnImuPackageReadyCallbackType callback) { m_impl->SetOnImuFPackageReadyCallBack(callback); }
        void ComputationManager::SetOnPpgPackageReadyCallBack(OnPpgPackageReadyCallbackType callback) { m_impl->SetOnPpgPackageReadyCallBack(callback); }

        void ComputationManager::EnableRecording() { m_impl->EnableRecording(); }
        void ComputationManager::DisableRecording() { m_impl->DisableRecording(); }
        bool ComputationManager::IsRecordingEnabled() { return  m_impl->IsRecordingEnabled(); }
        bool ComputationManager::StartRecording(const std::vector<RecordingDataType>& recordingTypes, const int recordingMaxTime) { return m_impl->StartRecording(recordingTypes, recordingMaxTime); }
        bool ComputationManager::StopRecording() { return m_impl->StopRecording(); }
        string ComputationManager::GetJsonRecording() { return m_impl->GetJsonRecording(); }
        void ComputationManager::SaveRecording() { m_impl->SaveRecording(); }
        void ComputationManager::RecordFSR(int data) { m_impl->RecordFSR(data); }
        void ComputationManager::RecordEvent(EventType eventType, const std::string& eventName) { m_impl->RecordEvent(eventType, eventName); }
        long ComputationManager::GetRecordingSize() const { return m_impl->GetRecordingSize(); }
        void ComputationManager::RecordEMGFusion(const std::string& data_tab, float data) { m_impl->RecordEMGFusion(data_tab, data); }
        void ComputationManager::AddVideo(const std::string& key, const std::string& videoPath) { m_impl->AddVideo(key, videoPath); }

    }
}
