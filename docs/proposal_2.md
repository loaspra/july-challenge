# Architecture Proposal 2: Big Data Containerized Solution with Apache Spark

## Overview
A scalable containerized big data architecture using Apache Spark for data processing, Apache Kafka for streaming ingestion, and a modern data lakehouse approach. This solution is designed to handle massive datasets and provide real-time analytics capabilities.

## Core Architecture

### Technology Stack
- **API Framework**: Spring Boot (Java) with reactive programming
- **Data Processing**: Apache Spark (PySpark/Scala)
- **Message Streaming**: Apache Kafka + Kafka Connect
- **Database**: 
  - PostgreSQL (operational data)
  - Apache Iceberg (data lake tables)
  - MinIO (S3-compatible object storage)
- **Query Engine**: Apache Spark SQL + Trino/Presto
- **Container Orchestration**: Kubernetes with Helm charts
- **Service Mesh**: Istio for microservices communication

### Container Services Architecture

#### 1. API Gateway Service (Spring Boot)
```dockerfile
FROM openjdk:17-jre-slim
# Reactive Spring WebFlux for high concurrency
# Handles CSV uploads and streaming to Kafka
# Serves analytics with caching layer
```

#### 2. Spark Cluster (Master + Workers)
```dockerfile
FROM apache/spark:3.4.0-scala2.12-java11-python3-ubuntu
# Spark master for job coordination
# Multiple Spark workers for parallel processing
# Custom Spark applications for CSV ingestion
```

#### 3. Kafka Cluster
```dockerfile
FROM confluentinc/cp-kafka:7.4.0
# High-throughput message streaming
# Topics for each data type (departments, jobs, employees)
# Kafka Connect for database integration
```

#### 4. Data Lake Storage (MinIO)
```dockerfile
FROM minio/minio:latest
# S3-compatible object storage
# Raw CSV files and processed parquet files
# Iceberg table metadata storage
```

#### 5. Query Engine (Trino)
```dockerfile
FROM trinodb/trino:latest
# Distributed SQL query engine
# Federated queries across data sources
# High-performance analytics
```

#### 6. Monitoring Stack
```dockerfile
# Prometheus + Grafana + Jaeger
# Spark History Server
# Kafka monitoring with Kafka UI
```

## Scalable Data Flow Architecture

### 1. High-Volume CSV Ingestion Flow
```
CSV Upload → API Gateway → Kafka Topic → Spark Streaming → Data Lake (Parquet/Iceberg)
                                     → Kafka Connect → PostgreSQL (operational)
```

### 2. Real-time Batch Operations Flow
```
API Request → Kafka Producer → Spark Structured Streaming → Batch Processing → Multi-sink Output
```

### 3. Analytics Query Flow
```
API Request → Trino Query Engine → Data Lake + PostgreSQL → Cached Results → JSON Response
```

## Data Lake Architecture (Lakehouse Pattern)

### Storage Layers
```
Raw Zone (Bronze):
├── csv-files/
│   ├── departments/
│   ├── jobs/
│   └── hired_employees/

Processed Zone (Silver):
├── parquet-tables/
│   ├── departments_cleaned/
│   ├── jobs_cleaned/
│   └── employees_cleaned/

Analytics Zone (Gold):
├── aggregated-tables/
│   ├── quarterly_hires/
│   ├── department_metrics/
│   └── employee_analytics/
```

### Iceberg Table Configuration
```sql
-- Employees table with partitioning and time travel
CREATE TABLE iceberg.analytics.hired_employees (
    id BIGINT,
    name VARCHAR,
    hire_datetime TIMESTAMP,
    department_id INT,
    job_id INT,
    hire_year INT,
    hire_quarter INT
) USING ICEBERG
PARTITIONED BY (hire_year, hire_quarter)
TBLPROPERTIES (
    'format-version' = '2',
    'write.parquet.compression-codec' = 'zstd'
)
```

## Kubernetes Deployment Architecture

### Namespace Structure
```yaml
# Development/Staging/Production namespaces
apiVersion: v1
kind: Namespace
metadata:
  name: globant-data-platform
  labels:
    environment: production
    team: data-engineering
```

### Spark Operator Configuration
```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: csv-ingestion-job
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: "globant/spark-app:latest"
  mainApplicationFile: "s3a://apps/csv_processor.py"
  sparkVersion: "3.4.0"
  driver:
    cores: 2
    memory: "4g"
    serviceAccount: spark-driver
  executor:
    cores: 4
    instances: 10
    memory: "8g"
  dynamicAllocation:
    enabled: true
    minExecutors: 2
    maxExecutors: 50
```

### Auto-scaling Configuration
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Advanced Data Processing Pipeline

### Spark Structured Streaming Application
```python
# CSV Processing with Delta Lake/Iceberg
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

spark = SparkSession.builder \
    .appName("CSVIngestionPipeline") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .getOrCreate()

# Schema enforcement and validation
employees_schema = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), False),
    StructField("datetime", TimestampType(), False),
    StructField("department_id", IntegerType(), True),
    StructField("job_id", IntegerType(), True)
])

# Streaming from Kafka with exactly-once semantics
df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "csv-employees") \
    .load()

# Data quality checks and transformations
processed_df = df.select(
    from_json(col("value").cast("string"), employees_schema).alias("data")
).select("data.*") \
.withColumn("hire_year", year(col("datetime"))) \
.withColumn("hire_quarter", quarter(col("datetime"))) \
.filter(col("id").isNotNull()) \
.dropDuplicates(["id"])

# Write to multiple sinks with different formats
query = processed_df.writeStream \
    .foreachBatch(write_to_multiple_sinks) \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://checkpoints/employees") \
    .start()
```

## API Endpoints with High Performance

### Reactive Spring Boot Controllers
```java
@RestController
@RequestMapping("/api/v2")
public class DataIngestionController {
    
    @PostMapping(value = "/upload/csv/{tableName}", 
                 consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<ResponseEntity<IngestionResponse>> uploadCSV(
        @PathVariable String tableName,
        @RequestPart("file") Mono<FilePart> filePart) {
        
        return filePart
            .flatMap(part -> csvProcessingService.processAsync(tableName, part))
            .map(result -> ResponseEntity.ok(result))
            .onErrorResume(error -> 
                Mono.just(ResponseEntity.badRequest()
                    .body(IngestionResponse.error(error.getMessage()))));
    }
    
    @PostMapping("/batch/{tableName}")
    public Mono<ResponseEntity<BatchResponse>> batchInsert(
        @PathVariable String tableName,
        @RequestBody Flux<Map<String, Object>> records) {
        
        return records
            .collectList()
            .flatMap(recordList -> 
                batchProcessingService.processBatch(tableName, recordList))
            .map(ResponseEntity::ok);
    }
}
```

### Advanced Analytics Endpoints
```java
@GetMapping("/analytics/quarterly-hires/{year}")
public Mono<ResponseEntity<List<QuarterlyHireStats>>> getQuarterlyHires(
    @PathVariable int year,
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "1000") int size) {
    
    return analyticsService
        .getQuarterlyHiresReactive(year, page, size)
        .collectList()
        .map(ResponseEntity::ok)
        .cache(Duration.ofMinutes(15)); // Cache for performance
}
```

## Scalability Features

### 1. Horizontal Scaling
- **Spark Workers**: Auto-scaling based on queue depth
- **Kafka Partitions**: Configurable parallelism
- **API Instances**: HPA based on CPU/memory/custom metrics
- **Storage**: Distributed across multiple MinIO nodes

### 2. Performance Optimizations
- **Data Skipping**: Iceberg metadata for efficient queries
- **Columnar Storage**: Parquet with compression
- **Predicate Pushdown**: Optimized query execution
- **Caching**: Multi-level caching (Redis, Spark, Application)

### 3. Fault Tolerance
- **Kafka Replication**: Multiple brokers with replication
- **Spark Checkpointing**: Automatic recovery from failures
- **Circuit Breakers**: Resilient API design
- **Health Checks**: Kubernetes liveness/readiness probes

## Monitoring and Observability

### Metrics Collection
```yaml
# Prometheus configuration for Spark metrics
- job_name: 'spark-applications'
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names:
          - globant-data-platform
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_label_app]
      regex: spark-.*
      action: keep
```

### Performance Dashboards
- **Spark Jobs**: Execution time, resource utilization
- **Kafka**: Throughput, lag, partition metrics
- **API Gateway**: Request rate, latency, error rate
- **Data Quality**: Schema validation, duplicate detection

## Data Governance and Security

### Access Control
```yaml
# RBAC for different user roles
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: data-engineer
rules:
- apiGroups: ["sparkoperator.k8s.io"]
  resources: ["sparkapplications"]
  verbs: ["get", "list", "create", "update", "patch"]
```

### Data Lineage
- **Iceberg**: Built-in metadata tracking
- **Spark**: Custom lineage extraction
- **API**: Request/response logging
- **OpenLineage**: Standard lineage format

## Deployment Strategy

### GitOps with ArgoCD
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: globant-data-platform
spec:
  source:
    repoURL: https://github.com/company/globant-challenge
    path: k8s
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: globant-data-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Environment Promotion
```
Development → Staging → Production
     ↓           ↓          ↓
   Minikube → EKS Dev → EKS Prod
```

## Advantages of This Approach

1. **Massive Scalability**: Handle petabyte-scale datasets
2. **Real-time Processing**: Sub-second latency for streaming data
3. **Cost Optimization**: Efficient resource utilization with auto-scaling
4. **Future-proof**: Modern data lakehouse architecture
5. **Multi-cloud**: Portable across cloud providers
6. **Advanced Analytics**: Support for ML and complex queries

## Performance Benchmarks

### Expected Throughput
- **CSV Ingestion**: 10GB+ files in <5 minutes
- **Batch Operations**: 100K+ records/second
- **Analytics Queries**: Sub-second response for complex aggregations
- **Concurrent Users**: 10K+ simultaneous API requests

### Resource Requirements
- **Development**: 16 CPU cores, 64GB RAM
- **Production**: 100+ CPU cores, 500GB+ RAM
- **Storage**: Unlimited with object storage scaling

This architecture demonstrates expertise in modern big data technologies, container orchestration, and scalable system design while maintaining hands-on implementation complexity.