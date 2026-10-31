/*!
 * /file WtRunner.cpp
 * /project	WonderTrader
 *
 * /author Wesley
 * /date 2020/03/30
 * 
 * /brief 
 */
#include "WtRunner.h"

#include "../WtCore/WtHelper.h"
#include "../WtCore/CtaStraContext.h"
#include "../WtCore/HftStraContext.h"
#include "../WtCore/WtDiffExecuter.h"

#include "../Includes/WTSVariant.hpp"
#include "../Includes/WTSContractInfo.hpp"
#include "../WTSTools/WTSLogger.h"
#include "../WTSUtils/WTSCfgLoader.h"
#include "../WTSUtils/SignalHook.hpp"
#include "../Share/StrUtil.hpp"
#include <csignal>

namespace
{
// C++ lock-free 原子操作可用于普通信号处理；处理函数不进入日志或对象调用。
static_assert(ATOMIC_BOOL_LOCK_FREE == 2, "Managed stop needs signal-safe lock-free bool");
std::atomic<bool> managedSignalRequested(false);
void requestManagedSignal(int) { managedSignalRequested.store(true); }
}


const char* getBinDir()
{
	static std::string basePath;
	if (basePath.empty())
	{
		basePath = boost::filesystem::initial_path<boost::filesystem::path>().string();

		basePath = StrUtil::standardisePath(basePath);
	}

	return basePath.c_str();
}



WtRunner::WtRunner()
	: _config(NULL)
	, _engine(NULL)
	, _data_store(NULL)
	, _is_hft(false)
	, _is_sel(false)
	, _to_exit(false)
	, _exit_code(0)
	, _managed_stop(false)
	, _configured(false)
	, _started(false)
	, _stop_begun(false)
	, _engine_stopped(false)
	, _stop_complete(false)
{
	install_signal_hooks([](const char* message) {
		WTSLogger::error(message);
	}, [this](bool bStopped) {
		_to_exit = bStopped;
		WTSLogger::info("Exit flag is {}", _to_exit.load());
	});
}


WtRunner::~WtRunner()
{
	if (_managed_stop)
	{
		// 未确认停止时保留整个成员依赖图，继续等待由插件负责的在途调用。
		while (!stop())
			std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
}

void WtRunner::init(const std::string& filename)
{
	WTSLogger::init(filename.c_str());

	WtHelper::setInstDir(getBinDir());

	if(!StdFile::exists(filename.c_str()))
	{
		WTSLogger::warn("logging configure {} not exists", filename);
	}
}

bool WtRunner::config(const std::string& filename)
{
	std::lock_guard<std::mutex> lifecycle(_lifecycle_mutex);
	try
	{
	if (_config || _started || _stop_complete)
		return false;
	_config = WTSCfgLoader::load_from_file(filename);
	if(_config == NULL)
	{
		WTSLogger::error("Loading config file {} failed", filename);
		return false;
	}

	WTSVariant* env = _config->get("env");
	_managed_stop = env && env->getBoolean("managed_stop");
	if (_managed_stop)
	{
		const char* mode = env->getCString("name");
		WTSVariant* risk = env->get("riskmon");
		WTSVariant* notifier = _config->get("notifier");
		if (notifier && notifier->getBoolean("active"))
		{
			WTSLogger::error("Managed stop requires an inactive notifier");
			return false;
		}
		if ((strlen(mode) && wt_stricmp(mode, "cta") != 0) || (risk && risk->getBoolean("active")))
		{
			WTSLogger::error("Managed stop requires CTA without an active risk monitor");
			return false;
		}
		for (const char* key : { "traders", "executers" })
		{
			WTSVariant* entries = _config->get(key);
			if (entries && (entries->type() != WTSVariant::VT_Array || entries->size() != 0))
			{
				WTSLogger::error("Managed stop requires an empty {} array", key);
				return false;
			}
		}
		// 受管模式当前使用内嵌 parser 列表，避免忽略外部配置加载失败。
		WTSVariant* parsers = _config->get("parsers");
		if (parsers && parsers->type() != WTSVariant::VT_Array)
			return false;
		managedSignalRequested.store(false);
		std::signal(SIGINT, requestManagedSignal);
		std::signal(SIGTERM, requestManagedSignal);
#ifdef _WIN32
		std::signal(SIGBREAK, requestManagedSignal);
#endif
	}

	//基础数据文件
	WTSVariant* cfgBF = _config->get("basefiles");
	if (cfgBF == NULL)
		return false;
	if (cfgBF->get("session"))
		_bd_mgr.loadSessions(cfgBF->getCString("session"));

	WTSVariant* cfgItem = cfgBF->get("commodity");
	if (cfgItem)
	{
		if (cfgItem->type() == WTSVariant::VT_String)
		{
			_bd_mgr.loadCommodities(cfgItem->asCString());
		}
		else if (cfgItem->type() == WTSVariant::VT_Array)
		{
			for (uint32_t i = 0; i < cfgItem->size(); i++)
			{
				_bd_mgr.loadCommodities(cfgItem->get(i)->asCString());
			}
		}
	}

	cfgItem = cfgBF->get("contract");
	if (cfgItem)
	{
		if (cfgItem->type() == WTSVariant::VT_String)
		{
			_bd_mgr.loadContracts(cfgItem->asCString());
		}
		else if (cfgItem->type() == WTSVariant::VT_Array)
		{
			for (uint32_t i = 0; i < cfgItem->size(); i++)
			{
				_bd_mgr.loadContracts(cfgItem->get(i)->asCString());
			}
		}
	}

	if (cfgBF->get("holiday"))
		_bd_mgr.loadHolidays(cfgBF->getCString("holiday"));

	if (cfgBF->get("hot"))
		_hot_mgr.loadHots(cfgBF->getCString("hot"));

	if (cfgBF->get("second"))
		_hot_mgr.loadSeconds(cfgBF->getCString("second"));

	WTSArray* ayContracts = _bd_mgr.getContracts();
	for (auto it = ayContracts->begin(); it != ayContracts->end(); it++)
	{
		WTSContractInfo* cInfo = (WTSContractInfo*)(*it);
		bool isHot = _hot_mgr.isHot(cInfo->getExchg(), cInfo->getCode());
		bool isSecond = _hot_mgr.isSecond(cInfo->getExchg(), cInfo->getCode());

		std::string hotCode = cInfo->getFullPid();
		if (isHot)
			hotCode += ".HOT";
		else if (isSecond)
			hotCode += ".2ND";
		else
			hotCode = "";

		cInfo->setHotFlag(isHot ? 1 : (isSecond ? 2 : 0), hotCode.c_str());
	}
	ayContracts->release();

	if (cfgBF->has("rules"))
	{
		auto cfgRules = cfgBF->get("rules");
		auto tags = cfgRules->memberNames();
		for (const std::string& ruleTag : tags)
		{
			_hot_mgr.loadCustomRules(ruleTag.c_str(), cfgRules->getCString(ruleTag.c_str()));
			WTSLogger::info("{} rules loaded from {}", ruleTag, cfgRules->getCString(ruleTag.c_str()));
		}
	}

	//初始化运行环境
	if (!initEngine())
		return false;

	//初始化数据管理
	if (!initDataMgr())
		return false;

	if (!initActionPolicy())
		return false;

	//初始化行情通道
	WTSVariant* cfgParser = _config->get("parsers");
	if (cfgParser)
	{
		if (cfgParser->type() == WTSVariant::VT_String)
		{
			const char* filename = cfgParser->asCString();
			if (StdFile::exists(filename))
			{
				WTSLogger::info("Reading parser config from {}...", filename);
				WTSVariant* var = WTSCfgLoader::load_from_file(filename);
				if(var)
				{
					if (!initParsers(var->get("parsers")))
						WTSLogger::error("Loading parsers failed");
					var->release();
				}
				else
				{
					WTSLogger::error("Loading parser config {} failed", filename);
				}
			}
			else
			{
				WTSLogger::error("Parser configuration {} not exists", filename);
			}
		}
		else if (cfgParser->type() == WTSVariant::VT_Array)
		{
			if (!initParsers(cfgParser) && _managed_stop)
				return false;
		}
	}

	//初始化交易通道
	WTSVariant* cfgTraders = _config->get("traders");
	if (cfgTraders)
	{
		if (cfgTraders->type() == WTSVariant::VT_String)
		{
			const char* filename = cfgTraders->asCString();
			if (StdFile::exists(filename))
			{
				WTSLogger::info("Reading trader config from {}...", filename);
				WTSVariant* var = WTSCfgLoader::load_from_file(filename);
				if (var)
				{
					if (!initTraders(var->get("traders")))
						WTSLogger::error("Loading traders failed");
					var->release();
				}
				else
				{
					WTSLogger::error("Loading trader config {} failed", filename);
				}
			}
			else
			{
				WTSLogger::error("Trader configuration {} not exists", filename);
			}
		}
		else if (cfgTraders->type() == WTSVariant::VT_Array)
		{
			initTraders(cfgTraders);
		}
	}

	initEvtNotifier();

	//如果不是高频引擎,则需要配置执行模块
	if (!_is_hft)
	{
		WTSVariant* cfgExec = _config->get("executers");
		if (cfgExec != NULL)
		{
			if (cfgExec->type() == WTSVariant::VT_String)
			{
				const char* filename = cfgExec->asCString();
				if (StdFile::exists(filename))
				{
					WTSLogger::info("Reading executer config from {}...", filename);
					WTSVariant* var = WTSCfgLoader::load_from_file(filename);
					if (var)
					{
						if (!initExecuters(var->get("executers")))
							WTSLogger::error("Loading executers failed");

						WTSVariant* c = var->get("routers");
						if (c != NULL)
							_cta_engine.loadRouterRules(c);

						var->release();
					}
					else
					{
						WTSLogger::error("Loading executer config {} failed", filename);
					}
				}
				else
				{
					WTSLogger::error("Trader configuration {} not exists", filename);
				}
			}
			else if (cfgExec->type() == WTSVariant::VT_Array)
			{
				initExecuters(cfgExec);
			}
		}

		WTSVariant* cfgRouter = _config->get("routers");
		if (cfgRouter != NULL)
			_cta_engine.loadRouterRules(cfgRouter);
	}

	if (_managed_stop && (!_parsers.supports_stop() || !_data_mgr.supports_stop()))
		return false;
	if (!_is_hft)
	{
		if (!initCtaStrategies() && _managed_stop)
			return false;
	}
	else
		initHftStrategies();
	_configured = true;
	return true;
	}
	catch (...)
	{
		_exit_code.store(1);
		WTSLogger::error("Runner configuration failed with exception");
		return false;
	}
}

bool WtRunner::initCtaStrategies()
{
	WTSVariant* cfg = _config->get("strategies");
	if (cfg == NULL || cfg->type() != WTSVariant::VT_Object)
		return false;

	cfg = cfg->get("cta");
	if (cfg == NULL || cfg->type() != WTSVariant::VT_Array)
		return false;

	std::string path = WtHelper::getCWD() + "cta/";
	_cta_stra_mgr.loadFactories(path.c_str());

	for (uint32_t idx = 0; idx < cfg->size(); idx++)
	{
		WTSVariant* cfgItem = cfg->get(idx);
		if (!cfgItem->getBoolean("active"))
			continue;

		const char* id = cfgItem->getCString("id");
		const char* name = cfgItem->getCString("name");
		int32_t slippage = cfgItem->getInt32("slippage");
		CtaStrategyPtr stra = _cta_stra_mgr.createStrategy(name, id);
		if (!stra || !stra->self())
			return false;
		if (!stra->self()->init(cfgItem->get("params")) && _managed_stop)
		{
			WTSLogger::error("Managed CTA strategy initialization failed");
			return false;
		}
		CtaStraContext* ctx = new CtaStraContext(&_cta_engine, id, slippage);
		ctx->set_strategy(stra->self());
		_cta_engine.addContext(CtaContextPtr(ctx));
	}

	return true;
}

bool WtRunner::initHftStrategies()
{
	WTSVariant* cfg = _config->get("strategies");
	if (cfg == NULL || cfg->type() != WTSVariant::VT_Object)
		return false;

	cfg = cfg->get("hft");
	if (cfg == NULL || cfg->type() != WTSVariant::VT_Array)
		return false;

	std::string path = WtHelper::getCWD() + "hft/";
	_hft_stra_mgr.loadFactories(path.c_str());

	for (uint32_t idx = 0; idx < cfg->size(); idx++)
	{
		WTSVariant* cfgItem = cfg->get(idx);
		if (!cfgItem->getBoolean("active"))
			continue;

		const char* id = cfgItem->getCString("id");
		const char* name = cfgItem->getCString("name");
		bool agent = cfgItem->getBoolean("agent");
		int32_t slippage = cfgItem->getInt32("slippage");
		HftStrategyPtr stra = _hft_stra_mgr.createStrategy(name, id);
		if (stra == NULL)
			continue;

		stra->self()->init(cfgItem->get("params"));
		HftStraContext* ctx = new HftStraContext(&_hft_engine, id, agent,slippage);
		ctx->set_strategy(stra->self());

		const char* traderid = cfgItem->getCString("trader");
		TraderAdapterPtr trader = _traders.getAdapter(traderid);
		if(trader)
		{
			ctx->setTrader(trader.get());
			trader->addSink(ctx);
		}
		else
		{
			WTSLogger::error("Trader {} not exists, binding trader to HFT strategy failed", traderid);
		}

		_hft_engine.addContext(HftContextPtr(ctx));
	}

	return true;
}


bool WtRunner::initEngine()
{
	WTSVariant* cfg = _config->get("env");
	if (cfg == NULL)
		return false;

	const char* name = cfg->getCString("name");
	
	if (strlen(name) == 0 || wt_stricmp(name, "cta") == 0)
	{
		_is_hft = false;
		_is_sel = false;
	}
	else if (wt_stricmp(name, "sel") == 0)
	{
		_is_sel = true;
	}
	else //if (wt_stricmp(name, "hft") == 0)
	{
		_is_hft = true;
	}

	if (_is_hft)
	{
		WTSLogger::info("Trading enviroment initialzied with engine: HFT");
		_hft_engine.init(cfg, &_bd_mgr, &_data_mgr, &_hot_mgr, &_notifier);
		_engine = &_hft_engine;
	}
	else if (_is_sel)
	{
		WTSLogger::info("Trading enviroment initialzied with engine: SEL");
		_sel_engine.init(cfg, &_bd_mgr, &_data_mgr, &_hot_mgr, &_notifier);
		_engine = &_sel_engine;
	}
	else
	{
		WTSLogger::info("Trading enviroment initialzied with engine: CTA");
		_cta_engine.init(cfg, &_bd_mgr, &_data_mgr, &_hot_mgr, &_notifier);
		_engine = &_cta_engine;
	}

	_engine->set_adapter_mgr(&_traders);

	return true;
}

bool WtRunner::initActionPolicy()
{
	return _act_policy.init(_config->getCString("bspolicy"));
}

bool WtRunner::initDataMgr()
{
	WTSVariant*cfg = _config->get("data");
	if (cfg == NULL)
		return false;

	if (!_data_mgr.init(cfg, _engine, false, _managed_stop))
		return false;
	WTSLogger::info("Data manager initialized");

	return true;
}

bool WtRunner::initParsers(WTSVariant* cfgParser)
{
	if (cfgParser == NULL)
		return false;

	uint32_t count = 0;
	for (uint32_t idx = 0; idx < cfgParser->size(); idx++)
	{
		WTSVariant* cfgItem = cfgParser->get(idx);
		if(!cfgItem->getBoolean("active"))
			continue;

		const char* id = cfgItem->getCString("id");
		// By Wesley @ 2021.12.14
		// 如果id为空，则生成自动id
		std::string realid = id;
		if (realid.empty())
		{
			static uint32_t auto_parserid = 1000;
			realid = StrUtil::printf("auto_parser_%u", auto_parserid++);
		}

		ParserAdapterPtr adapter(new ParserAdapter);
		// 先交给manager持有，初始化失败也通过同一停止链收束已创建对象。
		if (!_parsers.addAdapter(realid.c_str(), adapter))
			return false;
		if (!adapter->init(realid.c_str(), cfgItem, _engine, &_bd_mgr, &_hot_mgr, _managed_stop) && _managed_stop)
			return false;

		count++;
	}

	WTSLogger::info("{} parsers loaded", count);
	return true;
}

bool WtRunner::initExecuters(WTSVariant* cfgExecuter)
{
	if (cfgExecuter == NULL || cfgExecuter->type() != WTSVariant::VT_Array)
		return false;

	std::string path = WtHelper::getCWD() + "executer/";
	_exe_factory.loadFactories(path.c_str());

	uint32_t count = 0;
	for (uint32_t idx = 0; idx < cfgExecuter->size(); idx++)
	{
		WTSVariant* cfgItem = cfgExecuter->get(idx);
		if (!cfgItem->getBoolean("active"))
			continue;

		const char* id = cfgItem->getCString("id");
		std::string name = cfgItem->getCString("name");	//local,diff,dist
		if (name.empty())
			name = "local";

		if (name == "local")
		{
			WtLocalExecuter* executer = new WtLocalExecuter(&_exe_factory, id, &_data_mgr);
			if (!executer->init(cfgItem))
				return false;

			const char* tid = cfgItem->getCString("trader");
			if (strlen(tid) == 0)
			{
				WTSLogger::error("No Trader configured for Executer {}", id);
			}
			else
			{
				TraderAdapterPtr trader = _traders.getAdapter(tid);
				if (trader)
				{
					executer->setTrader(trader.get());
					trader->addSink(executer);
				}
				else
				{
					WTSLogger::error("Trader {} not exists, cannot configured for executer %s", tid, id);
				}
			}

			_cta_engine.addExecuter(ExecCmdPtr(executer));
		}
		else if (name == "diff")
		{
			WtDiffExecuter* executer = new WtDiffExecuter(&_exe_factory, id, &_data_mgr, &_bd_mgr);
			if (!executer->init(cfgItem))
				return false;

			const char* tid = cfgItem->getCString("trader");
			if (strlen(tid) == 0)
			{
				WTSLogger::error("No Trader configured for Executer {}", id);
			}
			else
			{
				TraderAdapterPtr trader = _traders.getAdapter(tid);
				if (trader)
				{
					executer->setTrader(trader.get());
					trader->addSink(executer);
				}
				else
				{
					WTSLogger::error("Trader {} not exists, cannot configured for executer %s", tid, id);
				}
			}

			_cta_engine.addExecuter(ExecCmdPtr(executer));
		}
		else
		{
			WtDistExecuter* executer = new WtDistExecuter(id);
			if (!executer->init(cfgItem))
				return false;

			_cta_engine.addExecuter(ExecCmdPtr(executer));
		}
		count++;
	}

	WTSLogger::info("{} executers loaded", count);

	return true;
}

bool WtRunner::initTraders(WTSVariant* cfgTrader)
{
	if (cfgTrader == NULL || cfgTrader->type() != WTSVariant::VT_Array)
		return false;
	
	uint32_t count = 0;
	for (uint32_t idx = 0; idx < cfgTrader->size(); idx++)
	{
		WTSVariant* cfgItem = cfgTrader->get(idx);
		if (!cfgItem->getBoolean("active"))
			continue;

		const char* id = cfgItem->getCString("id");

		TraderAdapterPtr adapter(new TraderAdapter(&_notifier));
		adapter->init(id, cfgItem, &_bd_mgr, &_act_policy);

		_traders.addAdapter(id, adapter);

		count++;
	}

	WTSLogger::info("{} traders loaded", count);

	return true;
}

void WtRunner::request_stop()
{
	_to_exit.store(true);
}

bool WtRunner::stop_requested()
{
	if (_managed_stop && _cta_engine.task_failure())
	{
		_exit_code.store(1);
		request_stop();
	}
	return _to_exit.load() || (_managed_stop && managedSignalRequested.load());
}

bool WtRunner::stop()
{
	request_stop();
	std::lock_guard<std::mutex> lifecycle(_lifecycle_mutex);
	if (!_managed_stop)
		return false;
	if (_stop_complete)
		return true;
	if (!_stop_begun)
	{
		_stop_begun = true;
		WTSLogger::info("Managed CTA stop begin");
	}
	_cta_engine.request_stop();
	if (!_parsers.stop(1000))
	{
		WTSLogger::warn("Managed CTA stop pending: parser");
		return false;
	}
	if (!_engine_stopped)
	{
		if (!_cta_engine.stop())
		{
			_exit_code.store(1);
			const auto stats = _cta_engine.task_stop_stats();
			WTSLogger::error("Managed CTA task drain failed: accepted={}, completed={}, failed={}, not_executed={}; failed task effects are unknown",
				stats.accepted, stats.completed, stats.failed, stats.not_executed);
		}
		_engine_stopped = true;
	}
	if (!_data_mgr.stop(1000))
	{
		WTSLogger::warn("Managed CTA stop pending: reader");
		return false;
	}
	_cta_stra_mgr.release();
	_cta_engine.release_contexts();
	_parsers.release();
	_data_mgr.release();
	if (_config) { _config->release(); _config = NULL; }
	_stop_complete = true;
	WTSLogger::info("Managed CTA stop complete");
	return true;
}

void WtRunner::run(bool bAsync /* = false */)
{
	try
	{
		{
			std::lock_guard<std::mutex> lifecycle(_lifecycle_mutex);
			if (!_configured || _started || _stop_begun)
			{
				_exit_code.store(1);
				return;
			}
			_started = true;
			const bool parsers_started = _parsers.run(_managed_stop);
			if (_managed_stop && !parsers_started)
			{
				_exit_code.store(1);
				request_stop();
				WTSLogger::error("Managed CTA parser start failed");
			}
			else
			{
				_traders.run();
				_engine->run();
			}
		}

		if(!bAsync)
		{
			while(!stop_requested())
			{
				std::this_thread::sleep_for(std::chrono::milliseconds(10));
			}
		}
	}
	catch (...)
	{
		_exit_code.store(1);
		request_stop();
		print_stack_trace([](const char* message) {
			WTSLogger::error(message);
		});
	}
	if (_managed_stop && (!bAsync || _exit_code.load() != 0))
	{
		while (!stop())
			std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
}

const char* LOG_TAGS[] = {
	"all",
	"debug",
	"info",
	"warn",
	"error",
	"fatal",
	"none"
};

void WtRunner::handleLogAppend(WTSLogLevel ll, const char* msg)
{
	_notifier.notify_log(LOG_TAGS[ll - 100], msg);
}

bool WtRunner::initEvtNotifier()
{
	WTSVariant* cfg = _config->get("notifier");
	if (cfg == NULL || cfg->type() != WTSVariant::VT_Object)
		return false;

	_notifier.init(cfg);

	return true;
}
