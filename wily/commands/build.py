"""
Builds a cache based on a source-control history

TODO : Convert .gitignore to radon ignore patterns to make the build more efficient.

"""
from progress.bar import Bar

from wily import logger
from wily.state import State
import wily.cache as cache


def build(config, archiver, operators):
    """
    Build the history given a archiver and collection of operators.

    :param config: The wily configuration
    :type  config: :namedtuple:`wily.config.WilyConfig`

    :param archiver: The archiver to use
    :type  archiver: :namedtuple:`wily.archivers.Archiver`

    :param operators: The list of operators to execute
    :type operators: `list` of :namedtuple:`wily.operators.Operator`
    """
    state = State(config, archiver)

    # Check for existence of cache, else provision
    state.ensure_exists()

    try:
        logger.debug(f"Using {archiver.name} archiver module")
        archiver = archiver.cls(config)
        revisions = archiver.revisions(config.path, config.max_revisions)
    except Exception as e:
        logger.error(f"Failed to setup archiver: '{e.message}'")
        exit(1)

    index = state.index

    # remove existing revisions from the list
    existing_revisions = index.revisions
    revisions = [
        revision for revision in revisions if revision.key not in existing_revisions
    ]

    logger.info(
        f"Found {len(revisions)} revisions from '{archiver.name}' archiver in '{config.path}'."
    )

    _op_desc = ",".join([operator.name for operator in operators])
    logger.info(f"Running operators - {_op_desc}")

    bar = Bar("Processing", max=len(revisions) * len(operators))
    try:
        for revision in revisions:
            # Checkout target revision
            archiver.checkout(revision, config.checkout_options)
            # Build a set of operators
            _operators = [operator.cls(config) for operator in operators]

            stats = {}
            stats["operator_data"] = {}
            for operator in _operators:
                logger.debug(f"Running {operator.name} operator on {revision.key}")
                stats["operator_data"][operator.name] = operator.run(revision, config)
                bar.next()
            index.add(revision)
            cache.store(config, archiver, revision, stats)
        index.save()
        bar.finish()
    except Exception as e:
        logger.error(f"Failed to build cache: '{e}'")
    finally:
        # Reset the archive after every run back to the head of the branch
        archiver.finish()
