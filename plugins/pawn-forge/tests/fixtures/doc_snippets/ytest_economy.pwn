// y_testing suite used by the run_server integration test: one passing, one failing test.
#define RUN_TESTS
#include <open.mp>
#include <YSI_Core\y_testing>

Economy_Payout(level)
{
	return level * 100;
}

@test() PayoutScalesWithLevel()
{
	ASSERT_EQ(Economy_Payout(1), 100);
	ASSERT_EQ(Economy_Payout(3), 300);
}

@test() PayoutIsCapped()
{
	ASSERT_LE(Economy_Payout(500), 10000); // intentionally failing: no cap implemented
}

main() {}
