#!/usr/bin/env python3
""" utility for exporting the results of the OpenMRS Concept Prevalence Study to a CSV file  """
# pylint: disable=too-many-arguments,
import argparse
import csv
import datetime
import logging
import os
import sys
from typing import Callable, Dict, Final, Iterable, List, NamedTuple

import mariadb

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(message)s"
# pylint: disable=invalid-name
utcnow: Final[Callable[[], datetime.datetime]] = datetime.datetime.utcnow


class DeferredException(NamedTuple):
    """
    contains information about an exception that occurred during program operation
    """

    timestamp: datetime.datetime
    exception_object: Exception


def execute_prevalence_query(
    cnxn: mariadb.Connection,
    file_name: str,
    output_dir: str,
    dialect: str,
    encoding: str = "utf8",
    chunksize: int = 1000,
    overwrite: bool = False,
) -> None:
    """
    given a database server connection and a list of table names, write a CSV
    file containing the complete contents of each table into the given output
    directory; the given csv.Dialect and character encoding are used to write
    the CSV output files
    """
    logging.debug("dumping table: %s", file_name)

    output_filename = os.path.join(output_dir, file_name.replace(".csv", "") + ".csv")
    if os.path.exists(output_filename):
        if overwrite:
            logging.warning(
                "%s: overwriting existing output file %s",
                file_name,
                output_filename,
            )
        else:
            logging.warning(
                "%s: skipping export because output file %s already exists",
                file_name,
                output_filename,
            )
            return

    # see https://mariadb-corporation.github.io/mariadb-connector-python/cursor.html
    cur = cnxn.cursor()
    cur.arraysize = chunksize

    sql_query = f"""SELECT
    c.concept_id AS concept_id,
    'concept' AS event_type,
    cn.name AS english_name,
    GROUP_CONCAT(
        CONCAT(
            REPLACE(REPLACE(crs.name, ',', '\\,'), ':', '\\:'),
            ':',
            REPLACE(REPLACE(crt.code, ',', '\\,'), ':', '\\:')
        )
        ORDER BY crs.name 
        SEPARATOR ', '
    ) AS mappings,
    cc.name AS class_name,
    cd.name AS datatype_name,
    c.retired AS is_retired,
    c.date_created AS date_created,
    null AS event_year,
    null AS n
FROM 
    concept c
JOIN 
    concept_name cn ON c.concept_id = cn.concept_id
JOIN 
    concept_class cc ON c.class_id = cc.concept_class_id
JOIN 
    concept_datatype cd ON c.datatype_id = cd.concept_datatype_id
LEFT JOIN 
    concept_reference_map crm ON c.concept_id = crm.concept_id
LEFT JOIN 
    concept_reference_term crt ON crm.concept_reference_term_id = crt.concept_reference_term_id
LEFT JOIN 
    concept_reference_source crs ON crt.concept_source_id = crs.concept_source_id
-- Join with obs and orders tables to filter concepts to those used within obs or orders
LEFT JOIN 
    (SELECT DISTINCT concept_id FROM obs WHERE voided = 0 
     UNION 
     SELECT DISTINCT value_coded AS concept_id FROM obs WHERE voided = 0 
     UNION 
     SELECT DISTINCT concept_id FROM orders WHERE voided = 0) used_concepts ON used_concepts.concept_id = c.concept_id
WHERE 
    cn.locale = 'en' 
    AND cn.concept_name_type = 'FULLY_SPECIFIED'
    AND cn.voided = 0
    AND used_concepts.concept_id IS NOT NULL
GROUP BY 
    c.concept_id, cn.name, cc.name, cd.name, c.retired, c.date_created

UNION ALL

-- Select counts of question concepts by year
SELECT 
    o.concept_id AS concept_id,
    'obs_concept' AS event_type,
    null AS english_name,
    null AS mappings,
    null AS class_name,
    null AS datatype_name,
    null AS retired,
    null AS date_created,
    YEAR(o.obs_datetime) AS event_year,
    COUNT(*) AS n
FROM 
    obs o
WHERE 
    o.voided = 0
GROUP BY 
    o.concept_id, event_year

UNION ALL

-- Select counts of coded value concepts by year
SELECT 
    o.value_coded AS concept_id,
    'obs_value' AS event_type,
    null AS english_name,
    null AS mappings,
    null AS class_name,
    null AS datatype_name,
    null AS retired,
    null AS date_created,
    YEAR(o.obs_datetime) AS event_year,
    COUNT(*) AS n
FROM 
    obs o
WHERE 
    o.value_coded IS NOT NULL
    AND o.voided = 0
GROUP BY 
    o.value_coded, event_year

UNION ALL

-- Select order concepts by year
SELECT 
    o.concept_id AS concept_id,
    'order' AS event_type,
    null AS english_name,
    null AS mappings,
    null AS class_name,
    null AS datatype_name,
    null AS retired,
    null AS date_created,
    YEAR(o.date_created) AS event_year,
    COUNT(*) AS n
FROM 
    orders o
WHERE 
    o.voided = 0
GROUP BY 
    o.concept_id, event_year"""

    cur.execute(
        sql_query,
        buffered=False,
    )
    fieldnames = [i[0] for i in cur.description]

    with open(output_filename, "w", newline="", encoding=encoding) as csvfile:
        writer = csv.writer(csvfile, dialect=dialect)
        writer.writerow(fieldnames)
        while data := cur.fetchmany():
            writer.writerows(data)
            logging.debug(
                "%s: wrote %s-row chunk to %s",
                file_name,
                len(data),
                output_filename,
            )
    logging.info(
        "%s: finished dumping results to %s (%s rows)",
        file_name,
        output_filename,
        cur.rowcount,
    )


def quoted_list(inlist: Iterable[str]) -> str:
    """
    return a joined, comma-separated version of the given list of strings with
    each member in double quotes; NOTE: NOT SAFE FOR UNTRUSTED INPUTS!
    """
    return ", ".join([f'"{item}"' for item in inlist])


def parse_bool(argument: str) -> bool:
    """parses the given argument string and returns a boolean evaluation"""
    return argument.lower().strip() in ("1", "enable", "on", "true", "y", "yes")


def log_config(args: argparse.Namespace) -> None:
    """
    given a parsed argument namespace, log it (while redacting the passwords
    """
    sensitive_items: Final = ("password",)

    logging.info("--- Begin Config Report ---")
    for k, v in vars(args).items():
        logging.info('"%s": "%s"', k, v if k not in sensitive_items else "-REDACTED-")
    logging.info("--- End Config Report ---")


def main() -> int:
    """
    entrypoint for direct execution; returns an integer suitable for use with sys.exit
    """
    # pylint: disable=protected-access
    log_level_choices = list(logging._nameToLevel)[:-1]
    dialect_choices = csv.list_dialects()

    argp = argparse.ArgumentParser(
        prog=__package__,
        description=(
            "generates a CSV file with results for the OpenMRS concept prevalence study"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    argp.add_argument(
        "--loglevel",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        metavar="LOG_LEVEL",
        choices=log_level_choices,
        help=(
            "determines how verbosely to log program operation; "
            f"possible values: {quoted_list(log_level_choices)}"
        ),
    )
    argp.add_argument(
        "--host",
        default=os.environ.get("DB_HOST", "127.0.0.1"),
        metavar="DB_HOST",
        help="network host to use when connecting to the database",
    )
    argp.add_argument(
        "--user",
        default=os.environ.get("DB_USER", "root"),
        metavar="DB_USER",
        help="username to use when connecting to the database",
    )
    argp.add_argument(
        "--password",
        default=os.environ.get("DB_PASSWORD", "password"),
        metavar="DB_PASSWORD",
        help="password string to use when connecting to the database",
    )
    argp.add_argument(
        "--database",
        default=os.environ.get("DB_DATABASE", "root"),
        metavar="DB_DATABASE",
        help="database name to use after connecting to the database",
    )
    argp.add_argument(
        "--chunksize",
        type=int,
        default=int(os.environ.get("CHUNK_SIZE", "1000")),
        metavar="CHUNK_SIZE",
        help=(
            "data retrieved from the server will be returned in chunks of this many "
            "rows; using a larger chunk size generally results in faster operation "
            "but uses more memory; selecting an excessive size will result in the "
            "program running out of memory"
        ),
    )
    argp.add_argument(
        "--path",
        default=os.environ.get("OUTPUT_PATH", os.getcwd()),
        metavar="OUTPUT_PATH",
        help="the base output path to use when creating CSV file",
    )
    argp.add_argument(
        "--csvdialect",
        default=os.environ.get("CSV_DIALECT", "unix"),
        metavar="CSV_DIALECT",
        choices=dialect_choices,
        help=(
            "python csv.writer dialect; "
            f"possible values: {quoted_list(dialect_choices)}; "
            "see: https://docs.python.org/3/library/csv.html#csv.Dialect"
        ),
    )
    argp.add_argument(
        "--csvencoding",
        default=os.environ.get("CSV_ENCODING", "utf8"),
        metavar="CSV_ENCODING",
        help="character encoding used when writing CSV file",
    )
    argp.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=parse_bool(os.environ.get("OVERWRITE", "0")),
        help=("if output file already exists, overwrite " "file instead of skipping"),
    )
    argp.add_argument(
        "--no-password",
        action="store_true",
        default=parse_bool(os.environ.get("NO_PASSWORD", "0")),
        help=(
            "indicates the database connection should be made without a "
            "password - this is distinct from an empty string password; if "
            "this argument and a password are given together the password "
            "argument will be ignored"
        ),
    )
    argp.add_argument(
        "--defer-exceptions",
        action=argparse.BooleanOptionalAction,
        default=parse_bool(os.environ.get("DEFER_EXCEPTIONS", "0")),
        help=(
            "indicates the program should attempt to keep running when a "
            "database error occurs; if this option is not enabled the program "
            "will halt immediately on error"
        ),
    )
    argp.add_argument(
        "--filename",
        default=os.environ.get("FILE_NAME", "concept-prevalence"),
        metavar="FILE_NAME",
        help=("name of CSV output file"),
    )
    args = argp.parse_args()
    logging.basicConfig(
        level=args.loglevel,
        format=LOG_FORMAT,
    )
    log_config(args)

    connect_args: Dict[str, str] = {
        "host": args.host,
        "user": args.user,
        "password": args.password,
        "database": args.database,
    }
    if args.no_password and "password" in connect_args:
        del connect_args["password"]

    deferred: List[DeferredException] = []

    # see: https://mariadb.com/kb/en/mysql_real_connect/ and
    # https://mariadb-corporation.github.io/mariadb-connector-python/module.html#mariadb.connect
    with mariadb.connect(**connect_args) as cnxn:
        try:
            execute_prevalence_query(
                cnxn,
                args.filename,
                args.path,
                args.csvdialect,
                encoding=args.csvencoding,
                chunksize=args.chunksize,
                overwrite=args.overwrite,
            )
        except mariadb.Error as e:
            logging.warning(
                "%sdatabase exception: %s",
                "DEFERRING " if args.defer_exceptions else "",
                e,
            )
            if not args.defer_exceptions:
                return 1
            deferred.append(DeferredException(utcnow(), e))

    if deferred:
        logging.info("Re-printing previously-deferred database exceptions")
        for de in deferred:
            logging.error(
                "DEFERRED DATABASE EXCEPTION FROM %s: %s",
                de.timestamp,
                de.exception_object,
            )
        logging.info("exiting (after deferred exceptions)")
        return 1

    logging.info("exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
