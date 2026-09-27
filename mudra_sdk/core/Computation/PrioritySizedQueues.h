#pragma once

#include <queue>
#include <memory>

namespace Mudra::Computation
{

    template <class T, int SIZE, class QUEUE_TYPE>
    class GeneralSizedQueue
    {
    public:
        
        GeneralSizedQueue()
        {
            Clear();
        }
        
        ~GeneralSizedQueue() {};
        
        void Push(T value)
        {
            m_queue.push(value);
            if (m_queue.size() > SIZE)
            {
                //			float max = m_queue.front();
                m_queue.pop();
            }
        }
        
        void Clear()
        {
            m_queue = QUEUE_TYPE();
        }
        
        bool IsFull()
        {
            return m_queue.size() == SIZE;
        }
        
        
        T GetAverage()
        {
            T average = 0;
            
            auto queue = m_queue;
            while (!queue.empty())
            {
                average += queue.top();
                queue.pop();
            }
            
            return average / m_queue.size();
        }
        
        size_t GetSize() const { return m_queue.size(); }
        
        std::vector<T> GetValues()
        {
            std::vector<T> values(SIZE);
            
            auto queue = m_queue;
            while (!queue.empty())
            {
                values.push_back(queue.top());
                queue.pop();
            }
            
            return values;
        }
        
    protected:
        QUEUE_TYPE m_queue;
    };

    template <class T, int SIZE>
    class PriorityUpSizedQueue : public GeneralSizedQueue<T, SIZE, std::priority_queue<T>>
    {
    };

    template <class T, int SIZE>
    class PriorityDownSizedQueue : public GeneralSizedQueue < T, SIZE, std::priority_queue<T, std::vector<T>, std::greater<T>> >
    {
    };

}
