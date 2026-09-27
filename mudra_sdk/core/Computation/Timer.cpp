#include "Timer.h"

#include <iostream>
#include <iomanip>

using namespace Mudra::Computation;

Timer::Timer(const string& name, shared_ptr<Logger> logger, unsigned priod)
	: m_logger(logger), m_name(name), m_printPriod(priod)
{
}

Timer::~Timer()
{
}

void Timer::Start()
{
	//	InfoMessage(m_logger) << "\n" << m_name << " start timer";
	m_start = std::chrono::system_clock::now();
}

#ifdef _WINDOWS
#pragma warning(disable:4996)
#endif 

double Timer::GetElapsedTime()
{
	auto end = std::chrono::system_clock::now();

	std::chrono::duration<double> elapsed_seconds = (end - m_start);
	// 	std::time_t end_time = std::chrono::system_clock::to_time_t(end);

	return elapsed_seconds.count();
}

long Timer::GetMillisElapsedTime()
{

	// Get the current system time
	auto end = std::chrono::system_clock::now();

	// Convert the system time to milliseconds since epoch
	auto duration = (end - m_start);

	return std::chrono::duration_cast<std::chrono::milliseconds>(duration).count();
}

void Timer::Stop()
{
	m_time += GetElapsedTime();
	m_counter++;

	Print();

	if (m_counter == m_printPriod)
	{
		m_counter = 0;
		m_time = 0;
	}
}


void Timer::Print()
{
	if (m_printPriod == 1)
	{
		DebugMessage(m_logger) << m_name << ' ' << m_time * 1000 << "ms";
	}
	else if (m_printPriod != 1 && m_counter == m_printPriod)
	{
		DebugMessage(m_logger) << m_name << ' ' << m_time * 1000 << "ms" <<
			" num of samples = " << m_counter << " average = " << m_time / m_counter * 1000 << "ms";
	}

}

std::string Timer::getISO8601Timestamp() {
	auto now = std::chrono::system_clock::now();
	auto time_t_now = std::chrono::system_clock::to_time_t(now);
	auto tm_now = *std::gmtime(&time_t_now);

	std::ostringstream oss;
	oss << std::put_time(&tm_now, "%Y-%m-%dT%H:%M:%S");

	return oss.str() + "Z";
}

std::string Timer::getLocalISO8601Timestamp() {
	auto now = std::chrono::system_clock::now();
	auto time_t_now = std::chrono::system_clock::to_time_t(now);
	auto tm_now = *std::localtime(&time_t_now); // Get local time

	std::ostringstream oss;
	oss << std::put_time(&tm_now, "%Y-%m-%dT%H:%M:%S");

	return oss.str();
}