# Промпт для реализации сервиса маршрутизации

## Обзор

Необходимо реализовать сервис оптимизации маршрутов для двух основных сценариев:
1. **Планирование маршрутов продавца (TSP)** - оптимальный обход точек продаж
2. **Маршрутизация транспорта (VRPC)** - распределение доставок между транспортными средствами с учётом грузоподъёмности

Сервис использует **Google Or-Tools** для решения задач оптимизации и **OSRM** для получения реальных матриц расстояний/времени.

---

## Архитектура

### Слоистая структура

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Layer (Servlets)                 │
│  - Авторизация (Bearer Token)                           │
│  - Приём JSON запросов                                  │
│  - Возврат JSON ответов                                 │
├─────────────────────────────────────────────────────────┤
│                    Gateway Layer                         │
│  - Маршрутизация к нужному решателю                     │
│  - Преобразование входных данных                        │
├─────────────────────────────────────────────────────────┤
│                 Data Preparation Layer                   │
│  - Парсинг JSON в модели                                │
│  - Запросы к OSRM для матриц расстояний                 │
│  - Валидация данных                                     │
├─────────────────────────────────────────────────────────┤
│                    Solver Layer                          │
│  - Конфигурация Or-Tools                                │
│  - Решение задачи оптимизации                           │
│  - Формирование результата                              │
├─────────────────────────────────────────────────────────┤
│                    Or-Tools Engine                       │
│  - RoutingIndexManager                                  │
│  - RoutingModel                                         │
│  - Assignment                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Основные интерфейсы

### 1. RoutingGateway<T, K>

Точка входа для каждого типа решателя.

```java
public interface RoutingGateway<T, K> {
    /**
     * Генерирует оптимальный маршрут из входных данных
     * @param inputModel входные данные
     * @return результат оптимизации
     */
    K generate(T inputModel);
}
```

### 2. RoutingSolver<T, K>

Абстрактный базовый класс для всех решателей.

```java
public abstract class RoutingSolver<T, K> implements RoutingProvider<K> {
    protected RoutingIndexManager manager;
    protected RoutingModel routing;
    protected Assignment solution;
    protected T inputModel;

    public RoutingSolver(T inputModel) {
        this.inputModel = inputModel;
    }

    // Абстрактные методы для реализации
    public abstract void solve();
    public abstract K prepareResult();
}
```

### 3. DataPreparationTool<T>

Интерфейс подготовки данных.

```java
public interface DataPreparationTool<T> {
    /**
     * Подготавливает данные из JSON
     * @param args массив строк (обычно JSON)
     * @return подготовленная модель данных
     */
    T prepareData(String... args);
}
```

### 4. RoutingServlet

Базовый сервлет с авторизацией.

```java
public abstract class RoutingServlet extends HttpServlet {

    protected boolean checkAuthorization(HttpServletRequest request) {
        String authHeader = request.getHeader("Authorization");
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return false;
        }
        String token = authHeader.substring(7);
        return validateToken(token);
    }

    protected abstract void processRequest(HttpServletRequest req, HttpServletResponse resp);
}
```

---

## Модуль 1: Планирование маршрутов продавца (Salesperson Plan)

### Описание задачи

Оптимизация маршрута торгового представителя для посещения точек продаж с учётом:
- Интенсивности посещений (3 раза/неделю, 2 раза/неделю, 1 раз/неделю и т.д.)
- Времени работы каждой точки
- Планирования на 4 недели (по 6 рабочих дней)

### Входные данные (PlanInputModel)

```json
{
  "kind": "single",  // или "auto" для автоматической кластеризации
  "locations": [
    {
      "id": "loc_001",
      "latitude": 41.311081,
      "longitude": 69.240562,
      "intensity": "THREE_TIMES_A_WEEK",
      "visitDuration": 30,
      "workingDays": [1, 2, 3, 4, 5, 6]
    }
  ],
  "startLocation": {
    "latitude": 41.299496,
    "longitude": 69.240074
  }
}
```

### Интенсивность посещений (Intensity Enum)

```java
public enum Intensity {
    THREE_TIMES_A_WEEK(3),   // Пн, Ср, Пт
    TWO_TIMES_A_WEEK(2),     // Пн, Чт
    ONCE_A_WEEK(1),          // Любой день
    ONCE_IN_TWO_WEEKS(0.5),  // Раз в 2 недели
    ONCE_A_MONTH(0.25);      // Раз в месяц

    private final double coefficient;
}
```

### Алгоритм SinglePlanSolver

```
1. ПОДГОТОВКА:
   - Получить матрицу времени от OSRM
   - Добавить время посещения к каждому переходу
   - Создать RoutingIndexManager(locationsCount, 1, depotIndex)

2. НЕДЕЛЯ 1:
   День 1-2: Распределить локации с интенсивностью 3 раза/неделю
   День 3-4: Распределить оставшиеся + интенсивность 2 раза/неделю
   День 5-6: Финализация недели

3. НЕДЕЛИ 2-4:
   - Учитывать предыдущие посещения (CachedLocations)
   - Применять штрафы для уже посещённых локаций
   - Запрещать посещение если превышена интенсивность

4. ОПТИМИЗАЦИЯ Or-Tools:
   - FirstSolutionStrategy: PATH_CHEAPEST_ARC
   - LocalSearchMetaheuristic: GUIDED_LOCAL_SEARCH
   - Dimension: "Time" с ограничением рабочего дня
```

### Алгоритм AutoPlanSolver (Кластеризация)

```
1. КЛАСТЕРИЗАЦИЯ:
   - Найти самую "левую" локацию (min longitude)
   - Итеративно добавлять ближайшие локации (формула Хаверсина)
   - Когда достигнут лимит - начать новый кластер

2. РЕШЕНИЕ:
   - Для каждого кластера запустить SinglePlanSolver
   - Перекодировать индексы обратно в глобальные
   - Объединить результаты

3. ФОРМУЛА ХАВЕРСИНА:
   a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
   c = 2 × atan2(√a, √(1−a))
   distance = R × c  // R = 6371 км
```

### Результат (SinglePlanResult)

```json
{
  "code": 100,
  "weeks": [
    {
      "weekNumber": 1,
      "days": [
        {
          "dayNumber": 1,
          "route": ["loc_001", "loc_005", "loc_003"],
          "totalDuration": 240,
          "totalDistance": 15.5
        }
      ]
    }
  ]
}
```

---



---



### Polyline6 кодирование

```java
// Координаты кодируются с точностью 6 знаков после запятой
// Алгоритм: Google Polyline Algorithm с precision=6
String encoded = PolylineCodec.encode(coordinates, 6);
```

---

## Обработка ошибок

### Коды ошибок (RoutingExceptionFactory)

```java
public class RoutingExceptionFactory {
    public static final int SUCCESS = 100;
    public static final int INVALID_INPUT = 101;
    public static final int UNSUPPORTED_VEHICLE_TYPE = 102;
    public static final int OSRM_URL_NOT_FOUND = 103;
    public static final int OSRM_CONNECTION_ERROR = 104;
    public static final int OSRM_MATRIX_ERROR = 105;
    public static final int WEIGHT_EXCEEDS_CAPACITY = 106;
    public static final int ARC_COST_NOT_SET = 107;
    public static final int TIME_LIMIT_EXCEEDED = 108;
    public static final int NO_SOLUTION_FOUND = 109;
    public static final int UNEXPECTED_ERROR = 110;
    public static final int OUT_OF_MEMORY = 111;

    public static RoutingException create(int code, String message) {
        return new RoutingException(code, message);
    }
}
```

### Класс RoutingException

```java
public class RoutingException extends RuntimeException {
    private final int code;
    private final String message;

    public JSONObject toJSON() {
        return new JSONObject()
            .put("code", code)
            .put("message", message);
    }
}
```




---

## Рекомендации по реализации

### Производительность

1. **Кеширование матриц OSRM** - если одни и те же точки используются повторно
2. **Асинхронные запросы** - параллельные запросы к OSRM для разных типов транспорта
3. **Пулы потоков** - для обработки нескольких запросов одновременно
4. **Динамический Time Limit** - увеличивать время для больших задач

### Масштабируемость

1. **Кластеризация** - разбивать большие задачи (>100 точек) на кластеры
2. **Batch processing** - группировать мелкие запросы
3. **Горизонтальное масштабирование** - stateless сервис легко масштабируется

### Надёжность

1. **Retry логика** - повторные попытки при ошибках OSRM
2. **Таймауты** - ограничение времени ожидания внешних сервисов
3. **Graceful degradation** - fallback на Хаверсина если OSRM недоступен
4. **Валидация входных данных** - проверка всех параметров до начала расчётов

### Мониторинг

1. **Логирование** - время выполнения, количество точек, результат
2. **Метрики** - успешность решений, среднее время, ошибки OSRM
3. **Health checks** - проверка доступности OSRM

---

## Пример реализации простого решателя

```java
public class SimpleTSPSolver extends RoutingSolver<TSPInputModel, TSPResult> {

    public SimpleTSPSolver(TSPInputModel inputModel) {
        super(inputModel);
    }

    @Override
    public void solve() {
        int nodeCount = inputModel.getDistanceMatrix().length;

        // 1. Создание менеджера индексов
        manager = new RoutingIndexManager(nodeCount, 1, 0);

        // 2. Создание модели маршрутизации
        routing = new RoutingModel(manager);

        // 3. Регистрация callback расстояний
        int transitCallbackIndex = routing.registerTransitCallback(
            (long fromIndex, long toIndex) -> {
                int from = manager.indexToNode(fromIndex);
                int to = manager.indexToNode(toIndex);
                return inputModel.getDistanceMatrix()[from][to];
            }
        );

        // 4. Установка стоимости дуг
        routing.setArcCostEvaluatorOfAllVehicles(transitCallbackIndex);

        // 5. Параметры поиска
        RoutingSearchParameters params = main.defaultRoutingSearchParameters()
            .toBuilder()
            .setFirstSolutionStrategy(FirstSolutionStrategy.Value.PATH_CHEAPEST_ARC)
            .setLocalSearchMetaheuristic(LocalSearchMetaheuristic.Value.GUIDED_LOCAL_SEARCH)
            .setTimeLimit(Duration.newBuilder().setSeconds(30).build())
            .build();

        // 6. Решение
        solution = routing.solveWithParameters(params);

        if (solution == null) {
            throw RoutingExceptionFactory.create(109, "No solution found");
        }
    }

    @Override
    public TSPResult prepareResult() {
        List<Integer> route = new ArrayList<>();
        long totalDistance = 0;

        long index = routing.start(0);
        while (!routing.isEnd(index)) {
            route.add(manager.indexToNode(index));
            long previousIndex = index;
            index = solution.value(routing.nextVar(index));
            totalDistance += routing.getArcCostForVehicle(previousIndex, index, 0);
        }
        route.add(manager.indexToNode(index));

        return new TSPResult(100, route, totalDistance);
    }
}
```

---

## Чек-лист для реализации

- [ ] Настроить зависимости (Or-Tools, Gson, Servlet API)
- [ ] Реализовать базовые интерфейсы (RoutingGateway, RoutingSolver, DataPreparationTool)
- [ ] Реализовать клиент OSRM (OSRMRoute)
- [ ] Реализовать TSP решатель (SinglePlanSolver)
- [ ] Реализовать кластеризацию (AutoPlanSolver)
- [ ] Реализовать VRPC решатель (VRPCSolver)
- [ ] Реализовать HTTP сервлеты с авторизацией
- [ ] Реализовать обработку ошибок (RoutingException)
- [ ] Настроить web.xml
- [ ] Написать тесты
- [ ] Настроить мониторинг и логирование
- [ ] Развернуть OSRM сервер (или использовать публичный)
