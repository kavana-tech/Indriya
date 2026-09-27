#pragma once

#include <deque>
#include <memory>

namespace Mudra::Computation
{

    template <class T, int SIZE>
    class SizedQueue
    {
        
        typedef std::deque<T> QueueType;
        
    public:
        
        SizedQueue()
        {
            Clear();
        }
        
        ~SizedQueue() {};
        
        void Push(T value)
        {
            m_queue.push_back(value);
            if (m_queue.size() > SIZE)
            {
                m_queue.pop_front();
            }
        }
        
        void Clear()
        {
            m_queue = QueueType();
        }
        
        bool IsFull()
        {
            return m_queue.size() == SIZE;
        }
        
        T Sum()
        {
            T sum = 0;
            for (T t :m_queue) {
                sum = sum + t;
                
            }
            return sum;
        }
        
        T Average()
        {
            return Sum()/m_queue.size();
        }
        
        int Size()
        {
            return SIZE;
        }

        const QueueType &data() const
        {
            return m_queue;
        }

        QueueType &data() 
        {
            return m_queue;
        }

    private:
        QueueType m_queue;
    };
}
