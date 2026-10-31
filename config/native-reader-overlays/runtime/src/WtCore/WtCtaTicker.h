/*!
 * \file WtCtaTicker.h
 * \project	WonderTrader
 *
 * \author Wesley
 * \date 2020/03/30
 * 
 * \brief 
 */
#pragma once
#include <stdint.h>
#include <atomic>

#include "../Includes/WTSMarcos.h"
#include "../Share/StdUtils.hpp"

NS_WTP_BEGIN
class WTSSessionInfo;
class IDataReader;
class WTSTickData;

class WtCtaEngine;
//////////////////////////////////////////////////////////////////////////
//生产时间步进器
class WtCtaRtTicker
{
public:
	WtCtaRtTicker(WtCtaEngine* engine) 
		: _engine(engine)
		, _stopped(false)
		, _date(0)
		, _time(UINT_MAX)
		, _next_check_time(0)
		, _last_emit_pos(0)
		, _cur_pos(0){}
	~WtCtaRtTicker(){}

public:
	void	init(IDataReader* store, const char* sessionID);
	//void	set_time(uint32_t uDate, uint32_t uTime);
	void	on_tick(WTSTickData* curTick);

	void	run();
	// 可从普通回调请求；唤醒计时等待，已进入的分钟回调整批完成。
	void	request_stop();
	// 控制线程等待 ticker 退出；重复/并发调用安全，worker 内调用仅请求停止。
	void	stop();

	bool		is_in_trading() const;
	uint32_t	time_to_mins(uint32_t uTime) const;

private:
	void	trigger_price(WTSTickData* curTick);
	bool	wait_for_stop(uint32_t milliseconds);

private:
	WTSSessionInfo*	_s_info;
	WtCtaEngine*	_engine;
	IDataReader*	_store;

	uint32_t	_date;
	uint32_t	_time;

	uint32_t	_cur_pos;

	StdUniqueMutex	_mtx;
	std::atomic<uint64_t>	_next_check_time;
	std::atomic<uint32_t>	_last_emit_pos;

	std::atomic<bool> _stopped;
	StdThreadPtr	_thrd;
	StdUniqueMutex	_stop_wait_mutex;
	StdCondVariable	_stop_wakeup;
	StdUniqueMutex	_join_mutex;
	std::thread::id	_worker_id;

};
NS_WTP_END
