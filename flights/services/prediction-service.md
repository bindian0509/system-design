# Price Prediction Service

## Overview

The Price Prediction Service provides ML-powered forecasts of future flight prices, helping users decide when to book. It answers the question: "Will prices go up or down in the next 7 days?"

---

## User Value

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Price Prediction UI                                  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  JFK → LAX  |  July 1, 2024  |  $299                                  │  │
│  │                                                                        │  │
│  │  📈 Prices likely to INCREASE by 12%                                  │  │
│  │  ⏰ Book now - prices typically rise within 7 days                    │  │
│  │  📊 Confidence: 78%                                                   │  │
│  │                                                                        │  │
│  │  [Book Now - $299]                                                     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Why we predict prices will rise:                                           │
│  • Search volume up 40% vs last week                                       │
│  • Only 21 days until departure                                            │
│  • Less than 10 seats remaining on most flights                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Price Prediction Service                              │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         API Layer                                     │   │
│  │  GET /routes/{route_id}/predict?departure_date=2024-07-01            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Feature Extractor                                │   │
│  │                                                                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │   Price     │  │   Search    │  │Availability │  │  Calendar   │  │   │
│  │  │  History    │  │  Velocity   │  │   Data      │  │   Events    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       Model Ensemble                                  │   │
│  │                                                                        │   │
│  │  ┌─────────────────────┐      ┌─────────────────────┐                │   │
│  │  │      XGBoost        │      │        LSTM         │                │   │
│  │  │    (Weight: 70%)    │      │    (Weight: 30%)    │                │   │
│  │  │                     │      │                     │                │   │
│  │  │  - Fast inference   │      │  - Sequence aware   │                │   │
│  │  │  - Feature importance│     │  - Trend patterns   │                │   │
│  │  │  - Handles missing  │      │  - Seasonality      │                │   │
│  │  └─────────────────────┘      └─────────────────────┘                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Prediction Aggregator                              │   │
│  │                                                                        │   │
│  │  - Weighted ensemble of model outputs                                 │   │
│  │  - Confidence calibration                                             │   │
│  │  - Recommendation generation                                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Response Builder                                 │   │
│  │                                                                        │   │
│  │  - Format prediction                                                  │   │
│  │  - Add explanations                                                   │   │
│  │  - Apply business rules                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Engineering

### Input Features

| Feature | Source | Description | Importance |
|---------|--------|-------------|------------|
| price_history_7d | ClickHouse | Last 7 days of prices | High |
| price_history_30d | ClickHouse | Last 30 days of prices | High |
| price_volatility | Derived | Std dev of recent prices | Medium |
| days_to_departure | Request | Calendar days until flight | High |
| search_velocity_1h | Redis | Searches in last hour | High |
| search_velocity_24h | Redis | Searches in last 24 hours | Medium |
| search_trend | Derived | 7d avg vs 30d avg | Medium |
| seats_remaining | Supplier | Avg seats across flights | High |
| seat_trend | Derived | Seat change over 24h | Medium |
| is_holiday | Calendar | Holiday at origin/dest | Medium |
| is_weekend_travel | Derived | Sat/Sun departure | Low |
| day_of_week | Request | 0-6 encoded | Low |
| month | Request | 1-12 encoded | Medium |
| route_popularity | Static | Historical route volume | Low |
| competitor_price_delta | External | Price vs competitors | Medium |

### Feature Extraction

```python
class FeatureExtractor:
    def __init__(self, clickhouse, redis, calendar):
        self.clickhouse = clickhouse
        self.redis = redis
        self.calendar = calendar

    def extract(self, route_id: str, departure_date: date) -> FeatureVector:
        features = {}

        # Price history features
        price_history = self.get_price_history(route_id, departure_date, days=90)
        features['price_mean_7d'] = np.mean(price_history[-7:])
        features['price_mean_30d'] = np.mean(price_history[-30:])
        features['price_std_7d'] = np.std(price_history[-7:])
        features['price_trend_7d'] = self.calculate_trend(price_history[-7:])
        features['price_min_90d'] = np.min(price_history)
        features['price_max_90d'] = np.max(price_history)
        features['price_percentile'] = self.calculate_percentile(
            price_history[-1], price_history
        )

        # Time features
        days_to_departure = (departure_date - date.today()).days
        features['days_to_departure'] = days_to_departure
        features['days_to_departure_log'] = np.log1p(days_to_departure)
        features['day_of_week'] = departure_date.weekday()
        features['month'] = departure_date.month
        features['is_weekend'] = departure_date.weekday() >= 5

        # Search velocity features
        search_data = self.redis.get_search_metrics(route_id)
        features['search_velocity_1h'] = search_data.searches_last_hour
        features['search_velocity_24h'] = search_data.searches_last_day
        features['search_velocity_7d'] = search_data.searches_last_week
        features['search_trend'] = (
            search_data.searches_last_week / 7
        ) / (search_data.searches_last_month / 30 + 0.1)

        # Availability features
        availability = self.get_availability(route_id, departure_date)
        features['seats_remaining_avg'] = availability.avg_seats
        features['seats_remaining_min'] = availability.min_seats
        features['flights_available'] = availability.flight_count

        # Calendar features
        features['is_holiday_origin'] = self.calendar.is_holiday(
            route_id.split('-')[0], departure_date
        )
        features['is_holiday_dest'] = self.calendar.is_holiday(
            route_id.split('-')[1], departure_date
        )
        features['days_to_nearest_holiday'] = self.calendar.days_to_holiday(
            departure_date
        )

        return FeatureVector(features)

    def get_price_history(self, route_id, departure_date, days):
        query = """
            SELECT
                toDate(recorded_at) as date,
                min(price_cents) as min_price
            FROM price_history
            WHERE route_id = %(route_id)s
              AND departure_date = %(departure_date)s
              AND recorded_at >= now() - INTERVAL %(days)s DAY
            GROUP BY date
            ORDER BY date
        """
        return self.clickhouse.execute(query, {
            'route_id': route_id,
            'departure_date': departure_date,
            'days': days
        })
```

---

## Model Architecture

### XGBoost Model (70% weight)

```python
class XGBoostPricePredictor:
    def __init__(self, model_path: str):
        self.model = xgb.Booster()
        self.model.load_model(model_path)

    def predict(self, features: FeatureVector) -> PredictionOutput:
        dmatrix = xgb.DMatrix(features.to_array())

        # Predict price change percentage
        prediction = self.model.predict(dmatrix)[0]

        # Get feature importance for explainability
        importance = self.model.get_score(importance_type='gain')

        return PredictionOutput(
            predicted_change_pct=prediction,
            confidence=self.calculate_confidence(features),
            feature_importance=importance
        )

    def calculate_confidence(self, features: FeatureVector) -> float:
        # Confidence is higher when:
        # - More historical data available
        # - Lower price volatility
        # - More days to departure (more data to observe)

        data_quality_score = min(features['price_history_count'] / 30, 1.0)
        volatility_penalty = min(features['price_std_7d'] / features['price_mean_7d'], 0.3)
        time_confidence = min(features['days_to_departure'] / 14, 1.0)

        confidence = (
            0.4 * data_quality_score +
            0.3 * (1 - volatility_penalty) +
            0.3 * time_confidence
        )

        return round(confidence, 2)
```

**XGBoost Hyperparameters:**

```python
xgb_params = {
    'objective': 'reg:squarederror',
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'min_child_weight': 3,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
}
```

### LSTM Model (30% weight)

For capturing sequential patterns in price movements:

```python
class LSTMPricePredictor:
    def __init__(self, model_path: str):
        self.model = tf.keras.models.load_model(model_path)
        self.sequence_length = 30  # 30 days of history

    def predict(self, price_sequence: np.ndarray) -> PredictionOutput:
        # Normalize sequence
        scaler = MinMaxScaler()
        normalized = scaler.fit_transform(price_sequence.reshape(-1, 1))

        # Reshape for LSTM: (batch, timesteps, features)
        input_data = normalized.reshape(1, self.sequence_length, 1)

        # Predict next 7 days
        predictions = []
        current_sequence = input_data.copy()

        for _ in range(7):
            next_pred = self.model.predict(current_sequence, verbose=0)
            predictions.append(next_pred[0, 0])
            # Roll sequence and add prediction
            current_sequence = np.roll(current_sequence, -1, axis=1)
            current_sequence[0, -1, 0] = next_pred[0, 0]

        # Inverse transform
        predictions = scaler.inverse_transform(
            np.array(predictions).reshape(-1, 1)
        ).flatten()

        # Calculate change from current to 7-day prediction
        current_price = price_sequence[-1]
        predicted_price = predictions[-1]
        change_pct = (predicted_price - current_price) / current_price * 100

        return PredictionOutput(
            predicted_change_pct=change_pct,
            predicted_prices_7d=predictions.tolist(),
            confidence=self.calculate_confidence(price_sequence)
        )
```

**LSTM Architecture:**

```python
model = tf.keras.Sequential([
    tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(30, 1)),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.LSTM(32, return_sequences=False),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(16, activation='relu'),
    tf.keras.layers.Dense(1)
])
```

### Ensemble Combination

```python
class EnsemblePredictor:
    def __init__(self, xgboost_model, lstm_model):
        self.xgboost = xgboost_model
        self.lstm = lstm_model
        self.xgboost_weight = 0.7
        self.lstm_weight = 0.3

    def predict(self, features: FeatureVector, price_sequence: np.ndarray) -> PredictionResult:
        # Get individual predictions
        xgb_pred = self.xgboost.predict(features)
        lstm_pred = self.lstm.predict(price_sequence)

        # Weighted ensemble
        ensemble_change = (
            self.xgboost_weight * xgb_pred.predicted_change_pct +
            self.lstm_weight * lstm_pred.predicted_change_pct
        )

        # Ensemble confidence (conservative)
        ensemble_confidence = min(xgb_pred.confidence, lstm_pred.confidence)

        # Determine direction
        if abs(ensemble_change) < 2:  # < 2% change
            direction = "stable"
        elif ensemble_change > 0:
            direction = "increase"
        else:
            direction = "decrease"

        return PredictionResult(
            direction=direction,
            predicted_change_pct=round(ensemble_change, 1),
            confidence=ensemble_confidence,
            xgboost_prediction=xgb_pred,
            lstm_prediction=lstm_pred
        )
```

---

## Prediction API

### Request

```http
GET /routes/{route_id}/predict?departure_date=2024-07-01
```

### Response

```json
{
  "route_id": "JFK-LAX",
  "departure_date": "2024-07-01",
  "current_price_cents": 29900,
  "prediction": {
    "direction": "increase",
    "predicted_change_percent": 12.5,
    "predicted_price_cents": 33640,
    "confidence": 0.78,
    "time_horizon_days": 7
  },
  "recommendation": {
    "action": "book_now",
    "message": "Prices are likely to rise by 12% in the next week. Book now for best value.",
    "urgency": "high"
  },
  "factors": [
    {
      "factor": "high_demand",
      "impact": "positive",
      "weight": 0.35,
      "description": "Search volume for this route is 40% above average"
    },
    {
      "factor": "approaching_departure",
      "impact": "positive",
      "weight": 0.30,
      "description": "Only 21 days until departure"
    },
    {
      "factor": "limited_seats",
      "impact": "positive",
      "weight": 0.25,
      "description": "Less than 10 seats remaining on most flights"
    },
    {
      "factor": "historical_pattern",
      "impact": "positive",
      "weight": 0.10,
      "description": "Prices typically rise for this route in early June"
    }
  ],
  "price_history": {
    "min_90d_cents": 24900,
    "max_90d_cents": 45900,
    "avg_90d_cents": 32500,
    "current_percentile": 25
  },
  "model_info": {
    "version": "v2.3.1",
    "last_trained": "2024-06-01T00:00:00Z",
    "accuracy_7d": 0.72
  },
  "generated_at": "2024-06-10T14:30:00Z"
}
```

---

## Recommendation Logic

```python
class RecommendationGenerator:
    def generate(self, prediction: PredictionResult, features: FeatureVector) -> Recommendation:
        # Only show predictions with sufficient confidence
        if prediction.confidence < 0.70:
            return Recommendation(
                action="monitor",
                message="Price trends are uncertain. Set a price alert to track changes.",
                urgency="low"
            )

        days_to_departure = features['days_to_departure']

        if prediction.direction == "increase":
            if prediction.predicted_change_pct > 15:
                return Recommendation(
                    action="book_now",
                    message=f"Prices are likely to rise significantly ({prediction.predicted_change_pct}%) soon. Book now for best value.",
                    urgency="high"
                )
            elif prediction.predicted_change_pct > 5:
                return Recommendation(
                    action="book_soon",
                    message=f"Prices may increase by {prediction.predicted_change_pct}% in the coming week.",
                    urgency="medium"
                )
            else:
                return Recommendation(
                    action="monitor",
                    message="Prices are relatively stable. Consider booking when ready.",
                    urgency="low"
                )

        elif prediction.direction == "decrease":
            if days_to_departure < 7:
                # Don't recommend waiting when departure is close
                return Recommendation(
                    action="book_soon",
                    message="While prices may drop slightly, don't wait too long with departure approaching.",
                    urgency="medium"
                )
            elif prediction.predicted_change_pct < -10:
                return Recommendation(
                    action="wait",
                    message=f"Prices may drop by {abs(prediction.predicted_change_pct)}%. Consider waiting a few days.",
                    urgency="low"
                )
            else:
                return Recommendation(
                    action="monitor",
                    message="Prices may decrease slightly. Set an alert for your target price.",
                    urgency="low"
                )

        else:  # stable
            return Recommendation(
                action="flexible",
                message="Prices are stable. Book when convenient.",
                urgency="low"
            )
```

---

## Model Training Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Training Pipeline                                   │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  ClickHouse  │───>│   Feature    │───>│   Training   │                   │
│  │  (Raw Data)  │    │  Engineering │    │   Dataset    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                 │                            │
│                                                 ▼                            │
│                      ┌──────────────────────────────────────────┐           │
│                      │           Train/Val/Test Split           │           │
│                      │         (70% / 15% / 15%)                │           │
│                      └──────────────────────────────────────────┘           │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                        │
│                    ▼               ▼               ▼                        │
│              ┌──────────┐   ┌──────────┐   ┌──────────┐                     │
│              │ XGBoost  │   │   LSTM   │   │ Ensemble │                     │
│              │ Training │   │ Training │   │  Tuning  │                     │
│              └──────────┘   └──────────┘   └──────────┘                     │
│                    │               │               │                        │
│                    └───────────────┼───────────────┘                        │
│                                    ▼                                         │
│                      ┌──────────────────────────────────────────┐           │
│                      │           Model Evaluation               │           │
│                      │  - MAE, RMSE, Direction Accuracy         │           │
│                      │  - Backtesting on historical data        │           │
│                      └──────────────────────────────────────────┘           │
│                                    │                                         │
│                                    ▼                                         │
│                      ┌──────────────────────────────────────────┐           │
│                      │           Model Registry                 │           │
│                      │        (MLflow / S3)                     │           │
│                      └──────────────────────────────────────────┘           │
│                                    │                                         │
│                                    ▼                                         │
│                      ┌──────────────────────────────────────────┐           │
│                      │      TensorFlow Serving / SageMaker      │           │
│                      └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Training Schedule

| Task | Frequency | Description |
|------|-----------|-------------|
| Full retraining | Daily (2 AM UTC) | Retrain on last 90 days |
| Incremental update | Hourly | Update with recent data |
| Model evaluation | Daily | Compare with baseline |
| A/B testing | Weekly | Test new model versions |

### Training Data Generation

```python
def generate_training_data(start_date, end_date):
    """
    Generate training examples from historical data.
    Each example: features at time T, target = price change in next 7 days
    """
    query = """
        WITH daily_prices AS (
            SELECT
                route_id,
                departure_date,
                toDate(recorded_at) as observation_date,
                min(price_cents) as min_price
            FROM price_history
            WHERE recorded_at BETWEEN %(start)s AND %(end)s
            GROUP BY route_id, departure_date, observation_date
        )
        SELECT
            t1.route_id,
            t1.departure_date,
            t1.observation_date,
            t1.min_price as current_price,
            t2.min_price as future_price,
            (t2.min_price - t1.min_price) / t1.min_price * 100 as price_change_pct
        FROM daily_prices t1
        JOIN daily_prices t2
            ON t1.route_id = t2.route_id
            AND t1.departure_date = t2.departure_date
            AND t2.observation_date = t1.observation_date + INTERVAL 7 DAY
        WHERE t1.observation_date BETWEEN %(start)s AND %(end)s - INTERVAL 7 DAY
    """
    return clickhouse.execute(query, {'start': start_date, 'end': end_date})
```

---

## Model Evaluation

### Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Direction Accuracy | > 65% | 72% |
| MAE (% change) | < 8% | 5.2% |
| RMSE (% change) | < 12% | 8.1% |
| Calibration Error | < 0.1 | 0.07 |

### Backtesting

```python
def backtest_model(model, test_data):
    """
    Evaluate model on historical data to measure real-world performance.
    """
    results = []

    for example in test_data:
        prediction = model.predict(example.features)
        actual_change = example.actual_price_change_pct

        results.append({
            'predicted_direction': 'increase' if prediction.change_pct > 0 else 'decrease',
            'actual_direction': 'increase' if actual_change > 0 else 'decrease',
            'predicted_change': prediction.change_pct,
            'actual_change': actual_change,
            'confidence': prediction.confidence,
            'correct_direction': (
                (prediction.change_pct > 0) == (actual_change > 0)
            )
        })

    # Calculate metrics
    df = pd.DataFrame(results)
    return {
        'direction_accuracy': df['correct_direction'].mean(),
        'mae': np.abs(df['predicted_change'] - df['actual_change']).mean(),
        'rmse': np.sqrt(((df['predicted_change'] - df['actual_change']) ** 2).mean()),
        'high_confidence_accuracy': df[df['confidence'] > 0.7]['correct_direction'].mean()
    }
```

---

## Serving Architecture

### TensorFlow Serving

```yaml
# model_config.proto
model_config_list {
  config {
    name: 'price_prediction_xgboost'
    base_path: 's3://models/price-prediction/xgboost'
    model_platform: 'tensorflow'
    model_version_policy {
      latest { num_versions: 2 }
    }
  }
  config {
    name: 'price_prediction_lstm'
    base_path: 's3://models/price-prediction/lstm'
    model_platform: 'tensorflow'
    model_version_policy {
      latest { num_versions: 2 }
    }
  }
}
```

### Caching Predictions

```python
class PredictionCache:
    def __init__(self, redis):
        self.redis = redis
        self.ttl = 300  # 5 minutes

    def get(self, route_id: str, departure_date: date) -> Optional[PredictionResult]:
        key = f"prediction:{route_id}:{departure_date}"
        cached = self.redis.get(key)
        if cached:
            return PredictionResult.from_json(cached)
        return None

    def set(self, route_id: str, departure_date: date, prediction: PredictionResult):
        key = f"prediction:{route_id}:{departure_date}"
        self.redis.setex(key, self.ttl, prediction.to_json())
```

---

## Metrics & Monitoring

```python
prediction_requests = prometheus.Counter(
    'prediction_requests_total',
    'Total prediction requests',
    ['route_type', 'confidence_bucket']
)

prediction_latency = prometheus.Histogram(
    'prediction_latency_seconds',
    'Prediction request latency',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

prediction_accuracy = prometheus.Gauge(
    'prediction_accuracy_7d',
    'Rolling 7-day prediction accuracy',
    ['model_version']
)

recommendation_distribution = prometheus.Counter(
    'recommendations_total',
    'Recommendation distribution',
    ['action', 'urgency']
)
```

---

## Configuration

```yaml
prediction_service:
  # Model settings
  models:
    xgboost:
      path: "s3://models/price-prediction/xgboost/latest"
      weight: 0.7
    lstm:
      path: "s3://models/price-prediction/lstm/latest"
      weight: 0.3
      sequence_length: 30

  # Prediction settings
  min_confidence_to_show: 0.70
  time_horizon_days: 7
  cache_ttl_seconds: 300

  # Feature extraction
  features:
    price_history_days: 90
    search_velocity_window_hours: 24

  # Training
  training:
    schedule: "0 2 * * *"  # Daily at 2 AM UTC
    data_retention_days: 90
    train_split: 0.7
    val_split: 0.15
    test_split: 0.15

  # Serving
  serving:
    max_batch_size: 100
    timeout_ms: 100
    replicas: 4
```
