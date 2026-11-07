# Cluster image changelog

## 2026-10-27
Rebuilt the worker image from the new base (Ubuntu 22.04).
Timezone is no longer forced to UTC in the image: it is taken from the host profile, which on the analytics hosts is America/New_York.
No change to Spark, Hadoop or Java versions.

## 2026-08-15
Security patches only.
