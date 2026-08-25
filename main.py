from resturaunt.orchestration import RestaurantOrchestrator, CustomerAgent, StockerAgent

# iniitialise the loop
tick = 0
tick_cost = 1000 # minimum time cost for each tick in milliseconds


restaurant_orchestrator = RestaurantOrchestrator(agents=[CustomerAgent(), StockerAgent()])
restaurant_orchestrator.run(max_ticks=1000)