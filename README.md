# omrs_conprev

This is a Docker utility for the **OpenMRS Concept Prevalence Study** *(based on the
[mysql2csv](https://github.com/edencehealth/mysql2csv) repo)*, which executes a query of an OpenMRS 
MySQL / MariaDB database and saves the result into a CSV file. It is published publicly to
[Docker Hub at edence/omrs_conprev](https://hub.docker.com/r/edence/omrs_conprev).
For more information about the **OpenMRS Concept Prevalence Study** please see 
[this post](https://talk.openmrs.org/t/help-us-make-openmrs-system-data-better-for-researchers/45088) on the 
OpenMRS TALK forum.

## Configuration

The program accepts its configuration from environment variables and
command-line arguments.

### Command-line Arguments

The program produces the following usage documentation when invoked with the
`--help` and `-h` command-line arguments:

```
usage: omrs_conprev [-h] [--loglevel LOG_LEVEL] [--host DB_HOST] [--user DB_USER]
                    [--password DB_PASSWORD] [--database DB_DATABASE]
                    [--chunksize CHUNK_SIZE] [--path OUTPUT_PATH]
                    [--csvdialect CSV_DIALECT] [--csvencoding CSV_ENCODING]
                    [--overwrite | --no-overwrite] [--no-password]
                    [--defer-exceptions | --no-defer-exceptions]
                    [--filename FILE_NAME]

generates CSV files from MySQL/MariaDB database tables

options:
  -h, --help            show this help message and exit
  --loglevel LOG_LEVEL  determines how verbosely to log program operation;
                        possible values: "CRITICAL", "FATAL", "ERROR", "WARN",
                        "WARNING", "INFO", "DEBUG" (default: INFO)
  --host DB_HOST        network host to use when connecting to the database
                        (default: 127.0.0.1)
  --user DB_USER        username to use when connecting to the database
                        (default: root)
  --password DB_PASSWORD
                        password string to use when connecting to the database
                        (default: password)
  --database DB_DATABASE
                        database name to use after connecting to the database
                        (default: root)
  --chunksize CHUNK_SIZE
                        data retrieved from the server will be returned in
                        chunks of this many rows; using a larger chunk size
                        generally results in faster operation but uses more
                        memory; selecting an excessive size will result in the
                        program running out of memory (default: 1000)
  --path OUTPUT_PATH    the base output path to use when creating CSV file
                        (default: <current directory>)
  --csvdialect CSV_DIALECT
                        python csv.writer dialect; possible values: "excel",
                        "excel-tab", "unix"; see:
                        https://docs.python.org/3/library/csv.html#csv.Dialect
                        (default: unix)
  --csvencoding CSV_ENCODING
                        character encoding used when writing CSV file
                        (default: utf8)
  --overwrite, --no-overwrite
                        if output file already exists, overwrite instead of skipping
                        (default: False)
  --no-password         indicates the database connection should be made
                        without a password - this is distinct from an empty
                        string password; if this argument and a password are
                        given together the password argument will be ignored
                        (default: False)
  --defer-exceptions, --no-defer-exceptions
                        indicates the program should attempt to keep running
                        when a database error occurs; if this option is not
                        enabled the program will halt immediately on error
                        (default: False)
```

#### Example Command-line Invocation

In this example we're running the OpenMRS Prevalence Study scripton an OpenMRS MySQL/MariaDB server on a host on the local network:

```sh
$ docker run --rm --volume "$(pwd):/output" edence/omrs_conprev:latest --host 192.168.1.123 --user root --password testing --database mysql --overwrite
2025-05-29 11:48:31,820 INFO concept-prevalence.csv: finished dumping results to /output/concept-prevalence.csv (964 rows)
2025-05-29 11:48:31,820 INFO exiting
```

### Docker Compose Configuration

Here is an example of how the image can be deployed in a docker compose file:

```yaml
services:
  omrs_conprev:
    environment:
      CHUNK_SIZE: 100000
      CSV_DIALECT: "excel"  # see also: unix ; https://docs.python.org/3/library/csv.html
      DB_DATABASE: "mysql"
      DB_HOST: "db"
      DB_PASSWORD: "testing"
      DB_USER: "root"
      LOG_LEVEL: "DEBUG"
      OVERWRITE: 1
      DEFER_EXCEPTIONS: 1
    volumes:
      - "./output:/output"
```
