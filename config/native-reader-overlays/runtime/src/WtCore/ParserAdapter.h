/*!
 * \file ParserAdapter.h
 * \project	WonderTrader
 *
 * \author Wesley
 * \date 2020/03/30
 * 
 * \brief 
 */
#pragma once
#include <memory>
#include <atomic>
#include <boost/core/noncopyable.hpp>

#include "../Includes/FasterDefs.h"
#include "../Includes/IParserApi.h"
#include "../Share/DLLHelper.hpp"


NS_WTP_BEGIN
class WTSVariant;
class IHotMgr;

class IParserStub
{
public:
	virtual void			handle_push_quote(WTSTickData* curTick){}

	virtual void			handle_push_order_detail(WTSOrdDtlData* curOrdDtl){}
	virtual void			handle_push_order_queue(WTSOrdQueData* curOrdQue) {}
	virtual void			handle_push_transaction(WTSTransData* curTrans) {}
};

class ParserAdapter : public IParserSpi,
					private boost::noncopyable
{
public:
	ParserAdapter();
	~ParserAdapter();

public:
	bool	init(const char* id, WTSVariant* cfg, IParserStub* stub, IBaseDataMgr* bgMgr, IHotMgr* hotMgr = NULL, bool require_stop = false);

	bool	initExt(const char* id, IParserApi* api, IParserStub* stub, IBaseDataMgr* bgMgr, IHotMgr* hotMgr = NULL);

	void	release();
	// 控制线程调用；false保留SPI和实例，全部生产者确认停止后才release。
	bool	supports_stop() const;
	bool	stop(uint32_t timeout_ms);

	// 默认保持原调用语义；true 要求传播插件连接失败。
	bool	run(bool require_connect_success = false);

	const char* id() const{ return _id.c_str(); }

public:
	virtual void handleSymbolList(const WTSArray* aySymbols) override {}

	/*
	 *	处理实时行情
	 *	@quote		实时行情
	 *	@bNeedSlice	是否需要切片,如果是从外部接入的快照行情数据,则需要切片,如果是内部广播的就不需要切片
	 */
	virtual void handleQuote(WTSTickData *quote, uint32_t procFlag) override;

	/*
	 *	处理委托队列数据（股票level2）
	 *	@ordQueData	委托对垒数据
	 */
	virtual void handleOrderQueue(WTSOrdQueData* ordQueData) override;

	/*
	 *	处理逐笔委托数据（股票level2）
	 *	@ordDetailData	逐笔委托数据
	 */
	virtual void handleOrderDetail(WTSOrdDtlData* ordDetailData) override;

	/*
		*	处理逐笔成交数据
		*	@transData	逐笔成交数据
		*/
	virtual void handleTransaction(WTSTransData* transData) override;

	virtual void handleParserLog(WTSLogLevel ll, const char* message) override;

	virtual IBaseDataMgr* getBaseDataMgr() override { return _bd_mgr; }


private:
	friend class ParserAdapterMgr;
	IParserApi*			_parser_api;
	FuncDeleteParser	_remover;
	typedef bool (*FuncStopParser)(IParserApi*, uint32_t);
	FuncStopParser		_stopper;
	DllHandle			_module;	// 保留到进程退出，最后tick/slice仍可调用模块代码。
	bool				_stop_requested;
	bool				_stop_confirmed;

	std::atomic<bool>	_stopped;

	/*
	 *	检查时间设置项
	 *	如果为true，则在收到行情的时候进行时间检查
	 *	主要适用于直接从行情源接入
	 *	因为直接从行情源接入很可能会有错误时间戳的数据进来
	 *	该选项默认为false
	 */
	bool				_check_time;

	typedef wt_hashset<std::string>	ExchgFilter;
	ExchgFilter			_exchg_filter;
	ExchgFilter			_code_filter;
	IBaseDataMgr*		_bd_mgr;
	IHotMgr*			_hot_mgr;
	IParserStub*		_stub;
	WTSVariant*			_cfg;
	std::string			_id;
};

typedef std::shared_ptr<ParserAdapter>	ParserAdapterPtr;
typedef wt_hashmap<std::string, ParserAdapterPtr>	ParserAdapterMap;

class ParserAdapterMgr : private boost::noncopyable
{
public:
	void	release();
	bool	supports_stop() const;
	bool	stop(uint32_t timeout_ms);

	// 默认保持原调用语义；true 要求传播插件连接失败。
	bool	run(bool require_connect_success = false);

	ParserAdapterPtr getAdapter(const char* id);

	bool	addAdapter(const char* id, ParserAdapterPtr& adapter);


public:
	ParserAdapterMap _adapters;
private:
	bool _stop_requested = false;
	bool _stop_confirmed = false;
};

NS_WTP_END
