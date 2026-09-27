#include <iostream>

#include "Logging.h"

using namespace Mudra::Computation;
using namespace std;


LogMessage::LogMessage(Logger::Severity severity, shared_ptr<Logger> logger)
	: m_severity(severity), m_logger(logger)
{
}

LogMessage::~LogMessage()
{
	m_logger->Msg(m_severity, str());
}

void Logger::Msg(Severity severity, const string &str)
{
	if (m_severityThreshold > severity)
	{
		return;
	}

 	if (m_msgCallBack)
	{
		m_msgCallBack(str);
		return;
	}

#ifdef _ANDROID
	android_LogPriority androidSeverity;

	switch (severity)
	{
	case Logger::Severity::Debug:
		androidSeverity = ANDROID_LOG_DEBUG;
		break;
	case Logger::Severity::Info:
		androidSeverity = ANDROID_LOG_INFO;
		break;
	case Logger::Severity::Warning:
		androidSeverity = ANDROID_LOG_WARN;
		break;
	case Logger::Severity::Error:
		androidSeverity = ANDROID_LOG_ERROR;
		break;
	default:
		androidSeverity = ANDROID_LOG_UNKNOWN;
		break;
	}

	__android_log_write(androidSeverity, m_tag.c_str(), str.c_str());
#else
	cout << endl << str;
#endif
 

}
