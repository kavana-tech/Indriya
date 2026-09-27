#pragma once

#include "CommonTypes.h"
#include "Logging.h"
#include "Timer.h"
#include "SizedQueues.h"

#include <queue>
#include <mutex>

namespace Mudra::Computation
{
    class SignalAnalyzer
    {
        FirmwareDataType m_dataType;
        shared_ptr<Logger> m_logger;
        Timer m_timer;
        int m_counterPerSecond;
        int m_frequency;

        static const unsigned int MAX_HISTORY_SIZE = 10;
        SizedQueue<double, MAX_HISTORY_SIZE> m_frequencyHistory;
        double m_frequencyStd;

    public:
        SignalAnalyzer(FirmwareDataType dataType, shared_ptr<Logger> logger);
        ~SignalAnalyzer();
        void compute(PackageData& PackageData);

    private:
        double calculateStandardDeviation();
    };
}
