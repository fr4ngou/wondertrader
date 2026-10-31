#include "../GuanhengExecution/ManagedTrader.h"
#include "../Includes/WTSMarcos.h"
extern "C"
{
EXPORT_FLAG wtp::ITraderApi* createTrader() { return new guanheng::ManagedTrader(guanheng::ProviderKind::Qmt); }
EXPORT_FLAG void deleteTrader(wtp::ITraderApi*& trader) { delete trader; trader = nullptr; }
}
