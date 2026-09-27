#pragma once

#include "CommonTypes.h"

#include <string>
#include <sstream>
#include <memory>

using namespace std;

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

#ifdef _ANDROID
#include <android/log.h>
#endif

namespace Mudra::Computation
{
    class Logger
    {
    public:
        enum class Severity
        {
            Debug,
            Info,
            Warning,
            Error
        };
        
        Logger(const string &tag, Severity severityThreshold) : m_tag(tag), m_severityThreshold(severityThreshold) {};
        
        friend class LogMessage;
        
        void SetSeverityThreshold(Severity severity) { m_severityThreshold = severity;}
        Severity GetSeverityThreshold() const { return m_severityThreshold; }
        void SetOnLoggingMessageCallBack(OnLoggingMessageCallBackType callback) { m_msgCallBack = callback; }
        
        void Debug(const string &str) { Msg(Severity::Debug, str); }
        void Info(const string &str) { Msg(Severity::Info, str); }
        void Warning(const string &str) { Msg(Severity::Warning, str); }
        void Error(const string &str) { Msg(Severity::Error, str); }
        
    private:
        string m_tag;
        
        void Msg(Severity severity, const string &str);
        
        Severity m_severityThreshold;
        
        OnLoggingMessageCallBackType m_msgCallBack;
    };


    class LogMessage : public basic_ostringstream<char>
    {
    public:
        DLLEXPORT LogMessage(Logger::Severity severity, shared_ptr<Logger> logger);
        DLLEXPORT ~LogMessage();
        
    private:
        Logger::Severity m_severity;
        shared_ptr<Logger> m_logger;
    };

    class DebugMessage : public LogMessage
    {
    public:
        DLLEXPORT DebugMessage(shared_ptr<Logger> logger) : LogMessage(Logger::Severity::Debug, logger) {};
    };

    class InfoMessage : public LogMessage
    {
    public:
        DLLEXPORT InfoMessage(shared_ptr<Logger> logger) : LogMessage(Logger::Severity::Info, logger) {};
    };

    class WarningMessage : public LogMessage
    {
    public:
        DLLEXPORT WarningMessage(shared_ptr<Logger> logger) : LogMessage(Logger::Severity::Warning, logger) {};
    };


    class ErrorMessage : public LogMessage
    {
    public:
        DLLEXPORT ErrorMessage(shared_ptr<Logger> logger) : LogMessage(Logger::Severity::Error, logger) {};
    };

    typedef LogMessage Log;
}

