#include "SignalAnalyzer.h"
#include <numeric>
#include <cmath>

using namespace Mudra::Computation;
using namespace std;

SignalAnalyzer::SignalAnalyzer(FirmwareDataType dataType, shared_ptr<Logger> logger) :
    m_logger(logger),
    m_dataType(dataType),
    m_timer("SignalStatsProcessor Timer", logger),
    m_counterPerSecond(0),
    m_frequency(0),
    m_frequencyStd(0.0) {
    m_timer.Start();
}

SignalAnalyzer ::~SignalAnalyzer() {
}

void SignalAnalyzer::compute(PackageData& packageData) {
    m_counterPerSecond++;

    if (m_timer.GetElapsedTime() > 1.0) {
        m_frequency = m_counterPerSecond;
        m_counterPerSecond = 0;
        m_timer.Start();
        m_frequencyHistory.Push(static_cast<double>(m_frequency));
        m_frequencyStd = calculateStandardDeviation();
    }

    packageData.frequency = m_frequency;
    packageData.frequencyStd = m_frequencyStd;
}

double SignalAnalyzer::calculateStandardDeviation() {

    double mean = m_frequencyHistory.Average();
    double variance = 0.0;

    for (const double& value : m_frequencyHistory.data()) {
        variance += (value - mean) * (value - mean);
    }
    variance /= m_frequencyHistory.Size();

    return sqrt(variance);
}
