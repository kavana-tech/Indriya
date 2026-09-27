#pragma once

#include <chrono>
#include <ctime>    
#include <memory>

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
    class Timer
    {
        std::chrono::system_clock::time_point m_start;
        
        shared_ptr<Logger> m_logger;
        std::string m_name;
        
        double m_time;
        unsigned m_counter = 0;
        unsigned m_printPriod = 1;
        
    public:
        DLLEXPORT Timer(const string& name, shared_ptr<Logger> logger, unsigned priod = 1);
        DLLEXPORT ~Timer();
        
        DLLEXPORT void Start();
        DLLEXPORT double GetElapsedTime();
        DLLEXPORT long GetMillisElapsedTime();
        void Stop();
        void Print();
        std::string getISO8601Timestamp();
        std::string getLocalISO8601Timestamp();
        double GetTime() const { return m_time; }
    };
}


