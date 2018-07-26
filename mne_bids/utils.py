"""Utility and helper functions for MNE-BIDS."""
# Authors: Mainak Jas <mainak.jas@telecom-paristech.fr>
#          Alexandre Gramfort <alexandre.gramfort@telecom-paristech.fr>
#          Teon Brooks <teon.brooks@gmail.com>
#          Chris Holdgraf <choldgraf@berkeley.edu>
#          Stefan Appelhoff <stefan.appelhoff@mailbox.org>
#
# License: BSD (3-clause)
import os
import errno
from collections import OrderedDict
import json
import shutil as sh

from .config import BIDS_VERSION

import numpy as np
from mne import read_events, find_events
from mne.externals.six import string_types

from .io import _parse_ext


def print_dir_tree(dir):
    """Recursively print a directory tree starting from `dir` [1].

    References
    ----------
    .. [1]

    """
    for root, dirs, files in os.walk(dir):
        path = root.split(os.sep)
        print((len(path) - 1) * '-----', os.path.basename(root))
        for file in files:
            print(len(path) * '-----', file)


def _mkdir_p(path, overwrite=False, verbose=False):
    """Create a directory, making parent directories as needed [1].

    References
    ----------
    .. [1] stackoverflow.com/questions/600268/mkdir-p-functionality-in-python

    """
    if overwrite is True and os.path.isdir(path):
        sh.rmtree(path)
        if verbose is True:
            print('Overwriting path: %s' % path)

    try:
        os.makedirs(path)
        if verbose is True:
            print('Creating folder: %s' % path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def make_bids_filename(subject=None, session=None, task=None,
                       acquisition=None, run=None, processing=None,
                       recording=None, space=None, suffix=None, prefix=None):
    """Create a BIDS filename from its component parts.

    BIDS filename prefixes have one or more pieces of metadata in them. They
    must follow a particular order, which is followed by this function. This
    will generate the *prefix* for a BIDS file name that can be used with many
    subsequent files, or you may also give a suffix that will then complete
    the file name.

    Note that all parameters are not applicable to each kind of data. For
    example, electrode location TSV files do not need a task field.

    Parameters
    ----------
    subject : str | None
        The subject ID. Corresponds to "sub".
    session : str | None
        The session for a item. Corresponds to "ses".
    task : str | None
        The task for a item. Corresponds to "task".
    acquisition: str | None
        The acquisition parameters for the item. Corresponds to "acq".
    run : int | None
        The run number for this item. Corresponds to "run".
    processing : str | None
        The processing label for this item. Corresponds to "proc".
    recording : str | None
        The recording name for this item. Corresponds to "recording".
    space : str | None
        The coordinate space for an anatomical file. Corresponds to "space".
    suffix : str | None
        The suffix of a file that begins with this prefix. E.g., 'audio.wav'.
    prefix : str | None
        The prefix for the filename to be created. E.g., a path to the folder
        in which you wish to create a file with this name.

    Returns
    -------
    filename : str
        The BIDS filename you wish to create.

    Examples
    --------
    >>> print(make_bids_filename(subject='test', session='two', task='mytask', suffix='data.csv')) # noqa
    sub-test_ses-two_task-mytask_data.csv

    """
    order = OrderedDict([('sub', subject),
                         ('ses', session),
                         ('task', task),
                         ('acq', acquisition),
                         ('run', run),
                         ('proc', processing),
                         ('space', space),
                         ('recording', recording)])
    if order['run'] is not None and not isinstance(order['run'], string_types):
        # Ensure that run is a string
        order['run'] = '{:02}'.format(order['run'])

    _check_types(order.values())

    if not any(isinstance(ii, string_types) for ii in order.keys()):
        raise ValueError("At least one parameter must be given.")

    filename = []
    for key, val in order.items():
        if val is not None:
            _check_key_val(key, val)
            filename.append('%s-%s' % (key, val))

    if isinstance(suffix, string_types):
        filename.append(suffix)

    filename = '_'.join(filename)
    if isinstance(prefix, string_types):
        filename = os.path.join(prefix, filename)
    return filename


def make_bids_folders(subject, session=None, kind=None, root=None,
                      make_dir=True, overwrite=True, verbose=False):
    """Create a BIDS folder hierarchy.

    This creates a hierarchy of folders *within* a BIDS dataset. You should
    plan to create these folders *inside* the root folder of the dataset.

    Parameters
    ----------
    subject : str
        The subject ID. Corresponds to "sub".
    kind : str
        The kind of folder being created at the end of the hierarchy. E.g.,
        "anat", "func", etc.
    session : str | None
        The session for a item. Corresponds to "ses".
    root : str | None
        The root for the folders to be created. If None, folders will be
        created in the current working directory.
    make_dir : bool
        Whether to actually create the folders specified. If False, only a
        path will be generated but no folders will be created.
    overwrite : bool
        If `make_dir` is True and one or all folders already exist,
        this will overwrite them with empty folders.
    verbose : bool
        If verbose is True, print status updates
        as folders are created.

    Returns
    -------
    path : str
        The (relative) path to the folder that was created.

    Examples
    --------
    >>> print(make_bids_folders('sub_01', session='my_session',
                                kind='meg', root='path/to/project', make_dir=False))  # noqa
    path/to/project/sub-sub_01/ses-my_session/meg

    """
    _check_types((subject, kind, session, root))
    if session is not None:
        _check_key_val('ses', session)

    path = ['sub-%s' % subject]
    if isinstance(session, string_types):
        path.append('ses-%s' % session)
    if isinstance(kind, string_types):
        path.append(kind)
    path = os.path.join(*path)
    if isinstance(root, string_types):
        path = os.path.join(root, path)

    if make_dir is True:
        _mkdir_p(path, overwrite=overwrite, verbose=verbose)
    return path


def make_dataset_description(path, name=None, data_license=None,
                             authors=None, acknowledgements=None,
                             how_to_acknowledge=None, funding=None,
                             references_and_links=None, doi=None,
                             verbose=False):
    """Create json for a dataset description.

    BIDS datasets may have one or more fields, this function allows you to
    specify which you wish to include in the description. See the BIDS
    documentation for information about what each field means.

    Parameters
    ----------
    path : str
        A path to a folder where the description will be created.
    name : str | None
        The name of this BIDS dataset.
    data_license : str | None
        The license under which this datset is published.
    authors : list | str | None
        List of individuals who contributed to the creation/curation of the
        dataset. Must be a list of strings or a single comma separated string
        like ['a', 'b', 'c'].
    acknowledgements : list | str | None
        Either a str acknowledging individuals who contributed to the
        creation/curation of this dataset OR a list of the individuals'
        names as str.
    how_to_acknowledge : list | str | None
        Either a str describing how to acknowledge this dataset OR a list of
        publications that should be cited.
    funding : list | str | None
        List of sources of funding (e.g., grant numbers). Must be a list of
        strings or a single comma separated string like ['a', 'b', 'c'].
    references_and_links : list | str | None
        List of references to publication that contain information on the
        dataset, or links.  Must be a list of strings or a single comma
        separated string like ['a', 'b', 'c'].
    doi : str | None
        The DOI for the dataset.

    Notes
    -----
    The required field BIDSVersion will be automatically filled by mne_bids.

    """
    # Put potential string input into list of strings
    if isinstance(authors, string_types):
        authors = authors.split(', ')
    if isinstance(funding, string_types):
        funding = funding.split(', ')
    if isinstance(references_and_links, string_types):
        references_and_links = references_and_links.split(', ')

    fname = os.path.join(path, 'dataset_description.json')
    description = OrderedDict([('Name', name),
                               ('BIDSVersion', BIDS_VERSION),
                               ('License', data_license),
                               ('Authors', authors),
                               ('Acknowledgements', acknowledgements),
                               ('HowToAcknowledge', how_to_acknowledge),
                               ('Funding', funding),
                               ('ReferencesAndLinks', references_and_links),
                               ('DatasetDOI', doi)])
    pop_keys = [key for key, val in description.items() if val is None]
    for key in pop_keys:
        description.pop(key)
    _write_json(description, fname, verbose=verbose)


def _check_types(variables):
    """Make sure all vars are str or None."""
    for var in variables:
        if not isinstance(var, (string_types, type(None))):
            raise ValueError("All values must be either None or strings. "
                             "Found type %s." % type(var))


def _write_json(dictionary, fname, verbose=False):
    """Write JSON to a file."""
    json_output = json.dumps(dictionary, indent=4)
    with open(fname, 'w') as fid:
        fid.write(json_output)
        fid.write('\n')

    if verbose is True:
        print(os.linesep + "Writing '%s'..." % fname + os.linesep)
        print(json_output)


def _check_key_val(key, val):
    """Perform checks on a value to make sure it adheres to the spec."""
    if any(ii in val for ii in ['-', '_', '/']):
        raise ValueError("Unallowed `-`, `_`, or `/` found in key/value pair"
                         " %s: %s" % (key, val))
    return key, val


def _read_events(events_data, raw):
    """Read in events data.

    Parameters
    ----------
    events_data : str | array | None
        The events file. If a string, a path to the events file. If an array,
        the MNE events array (shape n_events, 3). If None, events will be
        inferred from the stim channel using `find_events`.
    raw : instance of Raw
        The data as MNE-Python Raw object.

    Returns
    -------
    events : array, shape = (n_events, 3)
        The first column contains the event time in samples and the third
        column contains the event id. The second column is ignored for now but
        typically contains the value of the trigger channel either immediately
        before the event or immediately after.

    """
    if isinstance(events_data, string_types):
        events = read_events(events_data).astype(int)
    elif isinstance(events_data, np.ndarray):
        if events_data.ndim != 2:
            raise ValueError('Events must have two dimensions, '
                             'found %s' % events_data.ndim)
        if events_data.shape[1] != 3:
            raise ValueError('Events must have second dimension of length 3, '
                             'found %s' % events_data.shape[1])
        events = events_data
    else:
        events = find_events(raw)
    return events


def make_test_brainvision_data(output_dir='.', basename='test',
                               n_channels=2, fs=1000., rec_dur=10):
    """Make some test BrainVision data and save it to its multifile format.

    Parameters
    ----------
    output_dir : str
        Directory to which the .eeg, .vhdr, and .vmrk files will be written
    basename : str
        The basename of the files, to which only the extensions .eeg, .vhdr,
        and .vmrk will be appended
    n_channels : int
        Number of channels to put into the data. Will be labeled chani
        where i is a consecutive index
    fs : int
        Sampling frequency in Hz
    rec_dur : int
        Recording duration in seconds
    Returns
    -------
    vhdr : str
        Path to the header file

    """
    # Header data
    vhdr = os.path.join(output_dir, basename + '.vhdr')
    with open(vhdr, 'w') as f:
        f.write('Brain Vision Data Exchange Header File Version 1.0\n')
        f.write('\n[Common Infos]\n')
        f.write('DataFile=' + basename + '.eeg\n')
        f.write('MarkerFile=' + basename + '.vmrk\n')
        f.write('DataFormat=BINARY\n')
        f.write('Data orientation: MULTIPLEXED=ch1,pt1, ch2,pt1 ...\n')
        f.write('DataOrientation=MULTIPLEXED\n')
        f.write('NumberOfChannels=' + str(n_channels) + '\n')
        f.write('SamplingInterval=' + str(int(1./fs*1000.*1000.)) + '\n')
        f.write('\n[Binary Infos]\n')
        f.write('BinaryFormat=IEEE_FLOAT_32\n')
        f.write('\n[Channel Infos]\n')
        for channel in range(n_channels):
            f.write('Ch{0}=chan{0},,0.1\n'.format(channel+1))

    # Binary data
    eeg = os.path.join(output_dir, basename + '.eeg')
    data = 100 * np.random.randn(n_channels, int(rec_dur*fs))
    data = data.flatten(order='F')  # multiplexed
    data.astype('float32').tofile(eeg)

    # Marker data
    vmrk = os.path.join(output_dir, basename + '.vmrk')
    with open(vmrk, 'w') as f:
        f.write('Brain Vision Data Exchange Marker File, Version 1.0\n')
        f.write('\n[Common Infos]\n')
        f.write('DataFile=' + basename + '.eeg\n')
        f.write('\n[Marker Infos]\n')
        # Write one arbitrary event per second recording
        for event in range(rec_dur):
            f.write('Mk{}=Stimulus,S1,{},1,0\n'.format(event+1,
                                                       int(event*fs+0.5*fs)))

    return vhdr


def copyfile_brainvision(src, dest):
    """Copy a brainvision file to a new location and adjust pointers.

    The BrainVision format contains three files that have pointers
    to each other: '.eeg' for binary data, '.vhdr' for meta data
    as a header, and '.vmrk' for data on event markers. When renaming
    these files, the '.vhdr' and '.vmrk' files need to be edited to
    account for the new names and keep the pointers healthy.

    """
    if not os.path.exists(src):
        raise IOError('File does not exist: {}\n'.format(src))

    # Get extenstion of the brainvision file
    fname_src, ext_src = _parse_ext(src)
    fname_dest, ext_dest = _parse_ext(dest)
    if ext_src != ext_dest:
        raise ValueError('Need to move data with same extension'
                         ' but got {}, {}'.format(ext_src, ext_dest))
    ext = ext_src
    bv_ext = ['.eeg', '.vhdr', '.vmrk']
    if ext not in bv_ext:
        raise ValueError('Expecting file ending in one of {},'
                         ' but got {}'.format(bv_ext, ext))

    # .eeg is the binary file, we can just move it
    if ext == '.eeg':
        sh.copyfile(src, dest)
        return

    # .vhdr and .vmrk contain pointers. We need the basename
    # to change the pointers
    basename_src = fname_src.split(os.sep)[-1]
    basename_dest = fname_dest.split(os.sep)[-1]

    search_lines = ['DataFile=' + basename_src + '.eeg',
                    'MarkerFile=' + basename_src + '.vmrk']
    # Read the source
    with open(src, 'r') as f:
        lines = f.readlines()

    # Write new and replace relevant parts with new name
    with open(dest, 'w') as f:
        for line in lines:
            if line.strip() in search_lines:
                new_line = line.replace(basename_src,
                                        basename_dest)
                f.write(new_line)
            else:
                f.write(line)
