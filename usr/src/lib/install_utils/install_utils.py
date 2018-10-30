#!/usr/bin/python2.7
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

import ctypes as C
import sys
import os
import stat
import errno
import inspect
import select
import string
import crypt

# =============================================================================
# =============================================================================
"""
Install utility functions
"""
# =============================================================================
# =============================================================================


#==============================================================================
#==============================================================================
# Code used to parse an input string.  If no unescaped quotes or double-quotes
# are seen in the string, the whole string is returned in one token.  Quotes
# or double-quotes enveloping tokens break the input into the enveloped tokens.
# Quotes and double-quotes can be escaped with a \.  Unescaped quotes can be
# used inside double-quotes, and vice versa.
#
# Examples:
#   abc		-> [ abc ]		"abc" "def"	-> [ abc, def ]
#   "abc"	-> [ abc ]		"a'bc" "d\"ef"	-> [ a'bc, d"ef ]
#   abc def	-> [ abc, def ]		'a"bc' 'd\'ef'	-> [ a"bc, d'ef ]
#   "abc def"	-> [ abc def ]		"abc def" "ghi"	-> [ abc def, ghi ]
#   "a'b'c" 'd"e"f ghi'	-> [ a'b'c, d"e"f ghi ]
#==============================================================================
#==============================================================================

# States
(
__QST_START,	# Start
__QST_CHAR,	# Most chars and whitespace
__QST_ESC,	# escape (first backslash character)
__QST_SQT,	# Unescaped single quote
__QST_DQT	# Unescaped double quote
) = range(5)

# State table indices.
(
__QST_NONESC,	# Index used by start, char, sqt and dqt states
__QST_BSESC	# Index used by esc state
 ) = range(2)

# Next state indices.  These correspond to the current char which determines
# the next state.
(
__QST_CHAR_CHAR,	# Index in the tables corresp to char or whtsp recd
__QST_CHAR_BS,		# Index in the tables corresp to a backslash recd
__QST_CHAR_SQT,		# Index in the tables corresp to a single quote recd
__QST_CHAR_DQT		# Index in the tables corresp to a double quote recd
 ) = range(4)

# The state table

__QST_NONESC_TBL = []
__QST_NONESC_TBL.insert(__QST_CHAR_CHAR, __QST_CHAR)
__QST_NONESC_TBL.insert(__QST_CHAR_BS, __QST_ESC)
__QST_NONESC_TBL.insert(__QST_CHAR_SQT, __QST_SQT)
__QST_NONESC_TBL.insert(__QST_CHAR_DQT, __QST_DQT)

__QST_ESC_TBL = []
__QST_ESC_TBL.insert(__QST_CHAR_CHAR, __QST_CHAR)
__QST_ESC_TBL.insert(__QST_CHAR_BS, __QST_CHAR)
__QST_ESC_TBL.insert(__QST_CHAR_SQT, __QST_CHAR)
__QST_ESC_TBL.insert(__QST_CHAR_DQT, __QST_CHAR)

__SPACE_STATE_TABLE = []
__SPACE_STATE_TABLE.insert(__QST_NONESC, __QST_NONESC_TBL)
__SPACE_STATE_TABLE.insert(__QST_BSESC, __QST_ESC_TBL)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __space_next_state(curr_state, curr_char):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Find next state from space state table.  (Private function)

    Args:
      curr_state: Current state.  One of the state table states listed above

      curr_char: Current character.

    Returns: Next state.  One of the state table states listed above.

    Raises: N/A

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if (curr_state == __QST_ESC):
        idx = __QST_BSESC
    else:
        idx = __QST_NONESC
    if (curr_char == "\""):
        next_state = __SPACE_STATE_TABLE[idx][__QST_CHAR_DQT]
    elif (curr_char == "\'"):
        next_state = __SPACE_STATE_TABLE[idx][__QST_CHAR_SQT]
    elif (curr_char == "\\"):
        next_state = __SPACE_STATE_TABLE[idx][__QST_CHAR_BS]
    else:
        next_state = __SPACE_STATE_TABLE[idx][__QST_CHAR_CHAR]
    return next_state


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def space_parse(input_str):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Parse an input string into words, accounting for whitespace
        inside quoted (or double-quoted) strings.

    Quotes and double-quotes can be escaped with a \.  Unescaped quotes
    can be used inside double-quotes, and vice versa.

    Unescaped quotes and double-quotes are removed from the output.

    Escaped quotes and double-quotes are added to the output but their
    escaping \ are removed.

    Args:
      input_str: string to parse.

    Returns: list of parsed tokens.

    Raises: N/A

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Initialize.
    state = __QST_START
    word = ""
    outlist = []
    squoteon = False
    dquoteon = False
    input_str = input_str.strip()

    # Examine each character individually.
    for char in input_str:
        next_state = __space_next_state(state, char)

        # If previous state was escape and current char isn't a quote
        # being escaped, treat the previous backslash as a normal
        # character and append to the current word.
        if ((state == __QST_ESC) and
            ((char != "\"") and (char != "'"))):
            word += "\\"

        # Regular character
        if (next_state == __QST_CHAR):
            word += char

        # Escaped single quote
        elif (next_state == __QST_SQT):
            if (dquoteon):
                word += char
            else:
                squoteon = not squoteon
                if (not squoteon):
                    if (len(word) != 0):
                        outlist.append(word.strip())
                        word = ""

        # Escaped double quote
        elif (next_state == __QST_DQT):
            if (squoteon):
                word += char
            else:
                dquoteon = not dquoteon
                if (not dquoteon):
                    if (len(word) != 0):
                        outlist.append(word.strip())
                        word = ""

        elif (next_state != __QST_ESC):
            print >> sys.stderr, (
                                  "space_parse: Shouldn't get here!!!! " +
                                  "Char:%s, state:%d, next:%d" % (char, state,
                                  next_state))

        state = next_state

    # Done looping.  Handle the case of residual mismatched quotes or
    # double-quotes.
    if ((squoteon) or (dquoteon)):
        raise Exception("Unexpected unescaped quote found: " + input_str)

    # Handle the case where the \ is the last character of the input_str.
    if (state == __QST_ESC):
        word += "\\"

    # Flush any remaining word in progress.
    if (len(word) != 0):
        outlist.append(word.strip())

    return (outlist)


# =============================================================================
# =============================================================================
# Other utility functions
# =============================================================================
# =============================================================================

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def isnumber(arg):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Public function: does the (string) argument represent a number
        Hex, octal, decimal, floating point are all considered.
        Malformed numbers are considered not numeric.

    Test cases:
      0x123, .123, 0x.1, 0x0x123, 12.2, 12..3, 12.,  1.2.3, 1.23, 12z4, abc,
      0xabc, 0x1a2b3c4, 0xa2b3c4d, 0xabcdefg, 0xgabcdef, 0x123.

    Args:
      String value to evaluate

    Returns:
      True: string represents a number.
      False: string does not represent a numeric value.

    Raises: None

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    try:
        dummy = int(arg, 0)
        return True
    except ValueError:
        pass
    try:
        dummy = float(arg)
        return True
    except ValueError:
        pass
    return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def canaccess(filename, mode):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Test to see if can access filename with "mode" permissions

    If the file exists and can be accessed, just return.  Otherwise, throw
    an exception which contains appropriate errno value for proper error
    message.

    This method is needed because the chosen XML validator doesn't
    return an appropriate errno for its exit status, so file access needs
    to be checked independently.

    Args:
      filename: Name of the file to test for access

      mode: Character string mode, r=read, w=write, rw=read/write

    Returns: N/A

    Raises:
      IOError with the appropriate errno: file doesn't exist or doesn't
        have the permissions required for the requested access.
      IOError with errno = EINVAL: mode argument is invalid

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Don't try opening file with mode "w", else file will be truncated.
    if (mode == "rw"):
        mode = "a+"
    elif (mode == "w"):
        mode = "a"
    elif (mode != "r"):
        raise IOError((errno.EINVAL, os.strerror(errno.EINVAL) +
                        ": " + "mode"))

    dummy = os.stat(filename)		# Check for file existance.
    dummy = open(filename, mode)		# Check for file permissions.
    dummy.close()				# Clean up if you get here.


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __find_error_handler(raise_me):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Error handler for find() below.  Raises the exception passed to it.

    Args:
      raise_me: Exception to raise

    Returns: None

    Raises: The exception passed in.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    raise raise_me


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def find(rootpaths, path_type=None, raise_errors=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Python implementation of the Unix find(1) command.

    Order of output is similar, but not the same as, find(1) when -depth
    is not passed to it.  A directory is enumerated before the files it
    contains.

    Unlike find(1), no errors are returned when given a file or directory
    to parse which doesn't exist (when raise_errors is False)

    Args:
      rootpaths: list of file and/or directory pathnames to parse.

      path_type:
        - When set to None, return all found pathnames.
        - When set to "dir", return all found directories only.  This
            does not include links to directories.
        - When set to "file", return all found files only.  This does
            not include links to files.

     raise_errors:
        - When set to True: raise an OSError when a non-existant file
            or directory to parse is passed in the rootpaths list.
        - When set to False, ignore any such errors.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    rlist = []
    error_handler = None

    if ((path_type is not None) and (path_type != "dir") and
        (path_type != "file")):
        raise Exception(("find: \"path_type\" must be None, " +
                         "\"dir\" or \"file\""))

    if (raise_errors):
        error_handler = __find_error_handler

    for rootpath in rootpaths:

        try:
            stat_out = os.lstat(rootpath)
        except OSError:		# Doesn't exist
            continue

        # Handle case where rootpath is not a proper directory.
        # (Links to directories are not proper directories.)
        if ((path_type is None) and (not stat.S_ISDIR(stat_out.st_mode))):
            rlist.append(rootpath)
            continue

        # Print rootpath only if a proper file, if path_type == "file"
        elif (path_type == "file"):
            if (stat.S_ISREG(stat_out.st_mode)):
                rlist.append(rootpath)
            continue

        for path, subdirs, files in os.walk(rootpath, True,
                                            error_handler):

            # Take the path if we're taking everything, or if
            # path_type == dir and path is a proper directory (not link)
            if ((path_type is None) or
                ((path_type == "dir") and
                (stat.S_ISDIR(stat_out.st_mode)))):
                rlist.append(path)

            # Only the directory is desired.
            if (path_type == "dir"):
                continue

            # If names listed in subdirs are not directories (e.g.
            # they are symlinks), append them if path_type is None,
            # like what find(1) does.  If they are dirs, then
            # os.walk will get them on the next pass.
            if (path_type is None):
                for subdir in subdirs:
                    fullname = path + "/" + subdir
                    stat_out = os.lstat(fullname)
                    if (not stat.S_ISDIR(stat_out.st_mode)):
                        rlist.append(fullname)

            for one_file in files:
                fullname = path + "/" + one_file
                # Check for a proper file if (path_type == "file")
                if (path_type == "file"):
                    stat_out = os.lstat(fullname)
                    if (not stat.S_ISREG(stat_out.st_mode)):
                        continue
                rlist.append(fullname)
    return rlist


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def file_size(filename):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Get the size of the specified file/dir.

    If the size of a file/directory is not multiples of 1024, it's size
    will be rounded up to the next multiples of 1024.  This mimics the
    behavior of ufs especially with directories.  This results in a
    total size that's slightly bigger than if du was called on a ufs
    directory.

    The exception that will be raised by os.lstat() is intentionally
    not caught in this function so it can get passed to the caller
    and caller can deal with it.

    Args:
      filename: name of the file or directory to get the size for
        
    Returns:
        size of the file or directory in bytes.

    Raises:
        OSerror as returned from lstat.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # os.path.getsize() can't be used
    # here because that call follows symlinks, which is not
    # what we want to do. Use os.lstat() so symlinks are not
    # followed
    stat = os.lstat(filename)

    if (stat.st_size % 1024 == 0):
        return stat.st_size
    else:
        return (((stat.st_size / 1024) + 1) * 1024)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def dir_size(rootpath):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Estimates the size of the given directory.

    This function is similar in functionality to the "du" command,
    but this function works for both ufs and zfs.  
    On UFS, du(1) reports the size of the data blocks within the file.
    On ZFS, du(1) reports the actual size of the file as stored on disk.
    This size includes metadata as well as compression.  So, given
    exactly the same content for a directory, du reports different
    sizes depending on whether the directory is on UFS or ZFS.

    This function will traverse all the directories/files under a
    given directory, and add up the sizes for all the directories and files,
    and return the value in bytes.  
    
    Args:
      rootpath: root of the directory to calculate the size for

    Returns:
      Size of the directory contents in bytes.

    Raises:
      OSError as returned from file_size
      Exception: rootpath is not valid

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    size = 0

    # Get the size of the root directory
    size += file_size(rootpath)
    if (size == 0):
        # This indicates the root directory is not valid
        raise Exception((rootpath + "is not valid"))

    for root, subdirs, files in os.walk(rootpath):
        # There's no need to distinguish between directories and
        # files in the size calculation, merge the subdirs list
        # and files list to make rest of the code simpler.
        for filename in (files + subdirs):
            abs_filename = root + "/" + filename
            try:
                size += file_size(abs_filename)
            except OSError:
                # No need to exit because can't get size of
                # a file/dir, just print an error and continue
                print >> sys.stderr, \
                    ("Error getting information about "
                     + abs_filename)
                continue

    return (size)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def encrypt_password(plaintext, salt=None, alt_root="/", username=""):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Encrypts the password.  If a salt value is given, it will be used.
    If salt is not given, a salt will be generated for use.

    Args:
        plaintext: password string in plaintext
        salt: salt to be used for the encryption.  If none is provided,
              a salt will be generated.
        alt_root: alternate root to find the libc.so that contains the
                  libraries to be called for generating the seed.
        username: name of the user to generate the password for.

    Returns:
        The encrypted password string

    Raises:
        None
    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if salt is not None:
        return (crypt.crypt(plaintext, salt))

    # define needed structures for calling getpwnam(3C) and crypt_gensalt(3C)

    string = C.c_char_p

    class Passwd(C.Structure):
        _fields_ = [
            ("pw_name", string),
            ("pw_passwd", string),
            ("pw_uid", C.c_uint),
            ("pw_gid", C.c_uint),
            ("pw_age", string),
            ("pw_comment", string),
            ("pw_gecos", string),
            ("pw_dir", string),
            ("pw_shell", string)
        ]

    if sys.maxint == 2147483647:
        _LIBC = C.CDLL(os.path.join(alt_root, "usr/lib/libc.so"))
    else:
        _LIBC = C.CDLL(os.path.join(alt_root, "usr/lib/64/libc.so"))

    getpwnam = _LIBC.getpwnam
    getpwnam.argtypes = ((string),)
    getpwnam.restype = C.POINTER(Passwd)

    crypt_gensalt = _LIBC.crypt_gensalt
    crypt_gensalt.argtypes = (string, C.POINTER(Passwd))
    crypt_gensalt.restype = string

    pwnam_entry = getpwnam(username)
    salt = crypt_gensalt(None, pwnam_entry)

    return (crypt.crypt(plaintext, salt))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_argspec(func):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    '''Returns a tuple of (args, varargs, kwargs, defaults) with data
    on the call signature of any Python callable EXCEPT for builtins
    '''
    
    if not callable(func):
        raise TypeError("Not a callable Python function/object")
    
    if inspect.isfunction(func):
        return inspect.getargspec(func)
    elif hasattr(func, "im_func"):
        return inspect.getargspec(func.im_func)
    elif inspect.isclass(func):
        return inspect.getargspec(func.__init__)
    else:
        return inspect.getargspec(func.__call__)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def set_http_proxy(proxy):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    '''Set an http proxy in the environment.  Sets both upper and lower case
    versions of the variables to ensure coverage
    '''
    os.environ["HTTP_PROXY"] = proxy
    os.environ["http_proxy"] = proxy
