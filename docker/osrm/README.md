# OSRM Setup for Uzbekistan

## Download and Prepare Map Data

```bash
# Download Uzbekistan map from Geofabrik
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf -O uzbekistan-latest.osm.pbf

# Extract routing data
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf

# Partition the data
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm

# Customize for routing
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm
```

## Running OSRM

After preparation, start OSRM server:

```bash
docker run -t -i -p 5000:5000 -v $(pwd):/data osrm/osrm-backend osrm-routed --algorithm mld /data/uzbekistan-latest.osrm
```

## Testing

Test the routing service:

```bash
# Get route between two points in Tashkent
curl "http://localhost:5000/route/v1/driving/69.2401,41.2995;69.2787,41.3123?overview=full"
```
