"""
Created on 5.6.2013

:author: neriksso

"""
# Standard imports.
import urllib2

# Third party imports.
from lxml.etree import parse, ParseError, XMLSyntaxError
from wx import CallAfter

# Own imports.
import diwavars
from dialogs import UpdateDialog
import threads.common
from threads.diwathread import DIWA_THREAD


def logger():
    """ Get the common logger. """
    return threads.common.LOGGER


class CHECK_UPDATE(DIWA_THREAD):
    """
    Thread for checking version updates.

    """
    def __init__(self):
        DIWA_THREAD.__init__(self, name='VersionChecker')
        self.latest_version = ''

    @staticmethod
    def get_pad():
        """
        Returns the padfile object using PAD_URL setting.

        :returns:
            A Filelike object with additional methods geturl(), info() and
            getcode().

        """
        url = diwavars.PAD_URL
        logger().debug('CHECK_UPDATE called with pad-url: %s', url)
        result = None
        try:
            result = urllib2.urlopen(url)
        except urllib2.URLError:
            pass
        return result

    def show_dialog(self, url):
        """
        Shows the dialog that promps the user to download newer version of
        the software.

        :param url: URL address of the new version.
        :type url: String

        """
        try:
            dlg = UpdateDialog(self.latest_version, url)
            dlg.ShowModal()
            dlg.Destroy()
        except Exception, excp:
            logger().exception('Update Dialog Exception: %s', str(excp))

    def run(self):
        """
        Returns weather the update checking was successful.

        :rtype: Boolean

        """
        try:
            padfile = CHECK_UPDATE.get_pad()
            if padfile is None:
                logger().exception('Pad could not be found in URL.')
                return
            tree = parse(padfile)
        except urllib2.URLError:
            logger().exception('Update checker exception retrieving pad-file')
            return
        except XMLSyntaxError:
            logger().exception('Update checker exception parsing pad-file')
            return
        except ParseError:
            logger().exception('Update checker exception parsing pad-file')
            return
        except Exception, excp:
            logstr = 'Update checker exception, generic: %s'
            logger().exception(logstr, str(excp))
            return
        self.latest_version = tree.findtext('Program_Info/Program_Version')
        url_p = 'Proram_Info/Web_Info/Application_URLs/Primary_Download_URL'
        url_s = 'Proram_Info/Web_Info/Application_URLs/Secondary_Download_URL'
        url_primary = tree.findtext(url_p)
        url_secondary = tree.findtext(url_s)
        url = url_primary if url_primary else url_secondary
        if self.latest_version > diwavars.VERSION:
            CallAfter(self.show_dialog, url)