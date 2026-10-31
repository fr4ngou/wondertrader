/*!
 * \file ParserAdapter.cpp
 * \project	WonderTrader
 *
 * \author Wesley
 * \date 2020/03/30
 * 
 * \brief 
 */
#include "ParserAdapter.h"
#include "WtEngine.h"
#include "WtCtaTicker.h"
#include "WtHelper.h"

#include "../Share/CodeHelper.hpp"
#include "../Share/TimeUtils.hpp"

#include "../Includes/WTSContractInfo.hpp"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSVariant.hpp"
#include "../Includes/IBaseDataMgr.h"
#include "../Includes/IHotMgr.h"

#include "../WTSTools/WTSLogger.h"
#include <chrono>

USING_NS_WTP;

//////////////////////////////////////////////////////////////////////////
//ParserAdapter
ParserAdapter::ParserAdapter()
	: _parser_api(NULL)
	, _remover(NULL)
	, _stopper(NULL)
	, _module(NULL)
	, _stop_requested(false)
	, _stop_confirmed(false)
	, _stopped(false)
	, _check_time(false)
	, _bd_mgr(NULL)
	, _hot_mgr(NULL)
	, _stub(NULL)
	, _cfg(NULL)
{
}


ParserAdapter::~ParserAdapter()
{
	// 活实例由显式停止/释放路径管理，析构不在未知生产者线程上隐式join。
	if (_parser_api == NULL && _cfg) _cfg->release();
}

bool ParserAdapter::initExt(const char* id, IParserApi* api, IParserStub* stub, IBaseDataMgr* bgMgr, IHotMgr* hotMgr/* = NULL*/)
{
	if (api == NULL || _parser_api != NULL || _stop_requested)
		return false;

	_parser_api = api;
	_stub = stub;
	_bd_mgr = bgMgr;
	_hot_mgr = hotMgr;
	_id = id;

	if (_parser_api)
	{
		_parser_api->registerSpi(this);

		if (_parser_api->init(NULL))
		{
			ContractSet contractSet;
			WTSArray* ayContract = _bd_mgr->getContracts();
			WTSArray::Iterator it = ayContract->begin();
			for (; it != ayContract->end(); it++)
			{
				WTSContractInfo* contract = STATIC_CONVERT(*it, WTSContractInfo*);
				contractSet.insert(contract->getFullCode());
			}

			ayContract->release();

			_parser_api->subscribe(contractSet);
			contractSet.clear();
		}
		else
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_ERROR, "[{}] Parser initializing failed: api initializing failed...", _id.c_str());
			return false;
		}
	}

	return true;
}

bool ParserAdapter::init(const char* id, WTSVariant* cfg, IParserStub* stub, IBaseDataMgr* bgMgr, IHotMgr* hotMgr/* = NULL*/, bool require_stop/* = false*/)
{
	if (cfg == NULL || _parser_api != NULL || _stop_requested)
		return false;
	try
	{

	_stub = stub;
	_bd_mgr = bgMgr;
	_hot_mgr = hotMgr;
	_id = id;

	if (_cfg != NULL)
		return false;

	_cfg = cfg;
	_cfg->retain();

	_check_time = cfg->getBoolean("check_time");

	{
		//加载模块
		if (cfg->getString("module").empty())
			return false;

		std::string module = DLLHelper::wrap_module(cfg->getCString("module"), "lib");;

		//先看工作目录下是否有交易模块
		std::string dllpath = WtHelper::getModulePath(module.c_str(), "parsers", true);
		//如果没有,则再看模块目录,即dll同目录下
		if (!StdFile::exists(dllpath.c_str()))
			dllpath = WtHelper::getModulePath(module.c_str(), "parsers", false);

		DllHandle hInst = DLLHelper::load_library(dllpath.c_str());
		if (hInst == NULL)
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_ERROR, "[{}] Parser module {} loading failed", _id.c_str(), dllpath.c_str());
			return false;
		}
		else
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_INFO, "[{}] Parser module {} loaded", _id.c_str(), dllpath.c_str());
		}
		_module = hInst;
		_remover = (FuncDeleteParser)DLLHelper::get_symbol(hInst, "deleteParser");
		_stopper = (FuncStopParser)DLLHelper::get_symbol(hInst, "stopParser");
		if (require_stop && (!_remover || !_stopper))
		{
			WTSLogger::error("Parser {} has no managed stop/delete exports", _id.c_str());
			return false;
		}

		FuncCreateParser pFuncCreateParser = (FuncCreateParser)DLLHelper::get_symbol(hInst, "createParser");
		if (NULL == pFuncCreateParser)
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_FATAL, "[{}] Entrance function createParser not found", _id.c_str());
			return false;
		}

		_parser_api = pFuncCreateParser();
		if (NULL == _parser_api)
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_FATAL, "[{}] Creating parser api failed", _id.c_str());
			return false;
		}

	}
	

	const std::string& strFilter = cfg->getString("filter");
	if (!strFilter.empty())
	{
		const StringVector &ayFilter = StrUtil::split(strFilter, ",");
		auto it = ayFilter.begin();
		for (; it != ayFilter.end(); it++)
		{
			_exchg_filter.insert(*it);
		}
	}

	std::string strCodes = cfg->getString("code");
	if (!strCodes.empty())
	{
		const StringVector &ayCodes = StrUtil::split(strCodes, ",");
		auto it = ayCodes.begin();
		for (; it != ayCodes.end(); it++)
		{
			_code_filter.insert(*it);
		}
	}

	if (_parser_api)
	{
		_parser_api->registerSpi(this);

		if (_parser_api->init(cfg))
		{
			ContractSet contractSet;
			if (!_code_filter.empty())//优先判断合约过滤器
			{
				ExchgFilter::iterator it = _code_filter.begin();
				for (; it != _code_filter.end(); it++)
				{
					//全代码,形式如SSE.600000,期货代码为CFFEX.IF2005
					std::string code, exchg;
					auto ay = StrUtil::split((*it).c_str(), ".");
					if (ay.size() == 1)
						code = ay[0];
					else if (ay.size() == 2)
					{
						exchg = ay[0];
						code = ay[1];
					}
					else if (ay.size() == 3)
					{
						exchg = ay[0];
						code = ay[2];
					}
					WTSContractInfo* contract = _bd_mgr->getContract(code.c_str(), exchg.c_str());
					if(contract)
						contractSet.insert(contract->getFullCode());
					else
					{
						//如果是品种ID，则将该品种下全部合约都加到订阅列表
						WTSCommodityInfo* commInfo = _bd_mgr->getCommodity(exchg.c_str(), code.c_str());
						if(commInfo)
						{
							const auto& codes = commInfo->getCodes();
							for(const auto& c : codes)
							{
								contractSet.insert(fmt::format("{}.{}", exchg, c.c_str()));
							}							
						}
					}
				}
			}
			else if (!_exchg_filter.empty())
			{
				ExchgFilter::iterator it = _exchg_filter.begin();
				for (; it != _exchg_filter.end(); it++)
				{
					WTSArray* ayContract =_bd_mgr->getContracts((*it).c_str());
					WTSArray::Iterator it = ayContract->begin();
					for (; it != ayContract->end(); it++)
					{
						WTSContractInfo* contract = STATIC_CONVERT(*it, WTSContractInfo*);
						contractSet.insert(contract->getFullCode());
					}

					ayContract->release();
				}
			}
			else
			{
				WTSArray* ayContract =_bd_mgr->getContracts();
				WTSArray::Iterator it = ayContract->begin();
				for (; it != ayContract->end(); it++)
				{
					WTSContractInfo* contract = STATIC_CONVERT(*it, WTSContractInfo*);
					contractSet.insert(contract->getFullCode());
				}

				ayContract->release();
			}

			_parser_api->subscribe(contractSet);
			contractSet.clear();
		}
		else
		{
			WTSLogger::log_dyn("parser", _id.c_str(), LL_ERROR, "[{}] Parser initializing failed: api initializing failed...", _id.c_str());
			return false;
		}
	}
	else
	{
		WTSLogger::log_dyn("parser", _id.c_str(), LL_ERROR, "[{}] Parser initializing failed: creating api failed...", _id.c_str());
	}

	WTSLogger::log_dyn("parser", _id.c_str(), LL_INFO, "[{}] Parser initialzied, check_time: {}", _id.c_str(), _check_time);

	return true;
	}
	catch (...) { return false; }
}

void ParserAdapter::release()
{
	if (_stop_requested && !_stop_confirmed) return;
	_stopped = true;
	if (_parser_api)
	{
		_parser_api->release();
	}

	if (_parser_api)
	{
		if (_remover) _remover(_parser_api);
		else delete _parser_api;
		_parser_api = NULL;
	}
	if (_cfg) { _cfg->release(); _cfg = NULL; }
}

bool ParserAdapter::supports_stop() const
{
	return _parser_api != NULL && _stopper != NULL && _remover != NULL;
}

bool ParserAdapter::stop(uint32_t timeout_ms)
{
	if (_parser_api == NULL || _stop_confirmed) return true;
	if (!supports_stop()) return false;
	_stop_requested = true;
	try
	{
		if (!_stopper(_parser_api, timeout_ms)) return false;
	}
	catch (...) { return false; }
	_stop_confirmed = true;
	// 排空确认前继续允许最后已接纳的SPI；原子标志也覆盖旧release路径。
	_stopped.store(true);
	return true;
}

bool ParserAdapter::run(bool require_connect_success)
{
	if (_parser_api == NULL || _stop_requested || _stopped.load())
		return false;

	// 默认保留上游调用受理语义；受管启动显式检查连接结果。
	const bool connected = _parser_api->connect();
	return !require_connect_success || connected;
}

//合理毫秒数时间差
const int RESONABLE_MILLISECS = 60 * 60 * 1000;
void ParserAdapter::handleQuote(WTSTickData *quote, uint32_t procFlag)
{
	if (quote == NULL || _stopped || quote->actiondate() == 0 || quote->tradingdate() == 0)
		return;

	if (!_exchg_filter.empty() && (_exchg_filter.find(quote->exchg()) == _exchg_filter.end()))
		return;

	WTSContractInfo* cInfo = quote->getContractInfo();
	if (cInfo == NULL)
	{
		cInfo = _bd_mgr->getContract(quote->code(), quote->exchg());
		quote->setContractInfo(cInfo);
	}

	if (cInfo == NULL)
		return;

	WTSCommodityInfo* commInfo = cInfo->getCommInfo();
	WTSSessionInfo* sInfo = commInfo->getSessionInfo();

	if (_check_time)
	{
		int64_t tick_time = TimeUtils::makeTime(quote->actiondate(), quote->actiontime());
		int64_t local_time = TimeUtils::getLocalTimeNow();

		/*
		 *	By Wesley @ 2022.04.20
		 *	如果最新的tick时间，和本地时间相差太大
		 *	则认为tick的时间戳是错误的
		 *	这里要求本地时间是要时常进行校准的
		 */
		if (tick_time - local_time > RESONABLE_MILLISECS)
		{
			WTSLogger::warn("Tick of {} with wrong timestamp {}.{} received, skipped", cInfo->getFullCode(), quote->actiondate(), quote->actiontime());
			return;
		}
	}

	std::string stdCode;
	if (commInfo->getCategoty() == CC_FutOption || commInfo->getCategoty() == CC_SpotOption)
	{
		stdCode = CodeHelper::rawFutOptCodeToStdCode(cInfo->getCode(), cInfo->getExchg());
	}
	else if(CodeHelper::isMonthlyCode(quote->code()))
	{
		//如果是分月合约，则进行主力和次主力的判断
		stdCode = CodeHelper::rawMonthCodeToStdCode(cInfo->getCode(), cInfo->getExchg());
	}
	else
	{
		stdCode = CodeHelper::rawFlatCodeToStdCode(cInfo->getCode(), cInfo->getExchg(), cInfo->getProduct());
	}
	quote->setCode(stdCode.c_str());

	_stub->handle_push_quote(quote);
}

void ParserAdapter::handleOrderQueue(WTSOrdQueData* ordQueData)
{
	if (_stopped)
		return;

	if (!_exchg_filter.empty() && (_exchg_filter.find(ordQueData->exchg()) == _exchg_filter.end()))
		return;

	if (ordQueData->actiondate() == 0 || ordQueData->tradingdate() == 0)
		return;

	WTSContractInfo* cInfo = _bd_mgr->getContract(ordQueData->code(), ordQueData->exchg());
	if (cInfo == NULL)
		return;

	WTSCommodityInfo* commInfo = cInfo->getCommInfo();
	std::string stdCode = CodeHelper::rawFlatCodeToStdCode(cInfo->getCode(), cInfo->getExchg(), commInfo->getProduct());
	ordQueData->setCode(stdCode.c_str());

	if (_stub)
		_stub->handle_push_order_queue(ordQueData);
}

void ParserAdapter::handleOrderDetail(WTSOrdDtlData* ordDtlData)
{
	if (_stopped)
		return;

	if (!_exchg_filter.empty() && (_exchg_filter.find(ordDtlData->exchg()) == _exchg_filter.end()))
		return;

	if (ordDtlData->actiondate() == 0 || ordDtlData->tradingdate() == 0)
		return;

	WTSContractInfo* cInfo = _bd_mgr->getContract(ordDtlData->code(), ordDtlData->exchg());
	if (cInfo == NULL)
		return;

	WTSCommodityInfo* commInfo = cInfo->getCommInfo();
	std::string stdCode = CodeHelper::rawFlatCodeToStdCode(cInfo->getCode(), cInfo->getExchg(), commInfo->getProduct());
	ordDtlData->setCode(stdCode.c_str());

	if (_stub)
		_stub->handle_push_order_detail(ordDtlData);
}

void ParserAdapter::handleTransaction(WTSTransData* transData)
{
	if (_stopped)
		return;

	if (!_exchg_filter.empty() && (_exchg_filter.find(transData->exchg()) == _exchg_filter.end()))
		return;

	if (transData->actiondate() == 0 || transData->tradingdate() == 0)
		return;

	WTSContractInfo* cInfo = _bd_mgr->getContract(transData->code(), transData->exchg());
	if (cInfo == NULL)
		return;

	WTSCommodityInfo* commInfo = cInfo->getCommInfo();
	std::string stdCode = CodeHelper::rawFlatCodeToStdCode(cInfo->getCode(), cInfo->getExchg(), commInfo->getProduct());
	transData->setCode(stdCode.c_str());

	if (_stub)
		_stub->handle_push_transaction(transData);
}


void ParserAdapter::handleParserLog(WTSLogLevel ll, const char* message)
{
	if (_stopped)
		return;

	WTSLogger::log_dyn_raw("parser", _id.c_str(), ll, message);
}


//////////////////////////////////////////////////////////////////////////
//ParserAdapterMgr
void ParserAdapterMgr::release()
{
	if (_stop_requested && !_stop_confirmed) return;
	for (const auto& item : _adapters)
		if (item.second->_stop_requested && !item.second->_stop_confirmed) return;
	for (auto it = _adapters.begin(); it != _adapters.end(); it++)
	{
		it->second->release();
	}

	_adapters.clear();
}

bool ParserAdapterMgr::supports_stop() const
{
	for (const auto& item : _adapters)
		if (!item.second->supports_stop()) return false;
	return true;
}

bool ParserAdapterMgr::stop(uint32_t timeout_ms)
{
	if (_stop_confirmed) return true;
	_stop_requested = true;
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
	bool complete = true;
	for (const auto& item : _adapters)
	{
		const auto now = std::chrono::steady_clock::now();
		const auto remaining = now < deadline ? std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now).count() : 0;
		if (!item.second->stop(static_cast<uint32_t>(remaining))) complete = false;
	}
	_stop_confirmed = complete;
	return complete;
}

bool ParserAdapterMgr::addAdapter(const char* id, ParserAdapterPtr& adapter)
{
	if (adapter == NULL || strlen(id) == 0 || _stop_requested)
		return false;

	auto it = _adapters.find(id);
	if (it != _adapters.end())
	{
		WTSLogger::error(" Same name of parsers: {}", id);
		return false;
	}

	_adapters[id] = adapter;

	return true;
}


ParserAdapterPtr ParserAdapterMgr::getAdapter(const char* id)
{
	auto it = _adapters.find(id);
	if (it != _adapters.end())
	{
		return it->second;
	}

	return ParserAdapterPtr();
}

bool ParserAdapterMgr::run(bool require_connect_success)
{
	if (_stop_requested) return false;
	bool started = true;
	for (auto it = _adapters.begin(); it != _adapters.end(); it++)
	{
		if (!it->second->run(require_connect_success)) started = false;
	}

	WTSLogger::info("{} parsers started", _adapters.size());
	return started;
}
