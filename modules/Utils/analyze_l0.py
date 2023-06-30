import numpy as np
import matplotlib.pyplot as plt

class AnalyzeL0:

    """
    Description:
        This class contains functions to analyze L0 images (storing them
        as attributes) and functions to plot the results.

    Arguments:
        L0 - an L0 object

    Attributes:
        None so far
    """

    def __init__(self, L0, logger=None):
        self.L0 = L0
        if logger:
            self.logger = logger
            self.logger.debug('AnalyzeL0 class constructor')
        else:
            self.logger = None
            print('---->AnalyzeL0 class constructor')


    def plot_L0_stitched_image(self, ObsID, chip=None, fig_path=None, show_plot=False):
        L0 = self.L0
        """
        Generate a plot of the stitched L0 image.
        The image will be divided by 2^16, if appropriate.

        Args:
            chip (string) - "green" or "red"
            fig_path (string) - set to the path for a SNR vs. wavelength file
                to be generated.
            show_plot (boolean) - show the plot in the current environment.

        Returns:
            PNG plot in fig_path or shows the plot it the current environment
            (e.g., in a Jupyter Notebook).
        """

        starname = L0['PRIMARY'].header['TARGNAME']
        ObsID = L0['PRIMARY'].header['OFNAME']  # better to use header keywords than pass in ObsID
        
        if chip == 'green' or chip == 'red':
            if chip == 'green':
                CHIP = 'GREEN'
            if chip == 'red':
                CHIP = 'RED'
            # Determine the number of regions in image
            regions = 0
            amp1_present = False
            amp2_present = False
            amp3_present = False
            amp4_present = False
            for hdu in L0:
                if hdu.name == CHIP + '_AMP1':
                    amp1_present = True
                if hdu.name == CHIP + '_AMP2':
                    amp2_present = True
                if hdu.name == CHIP + '_AMP3':
                    amp3_present = True
                if hdu.name == CHIP + '_AMP4':
                    amp4_present = True
            if amp1_present:
                regions = 1
            if amp1_present & amp2_present:
                regions = 2
            if amp1_present & amp2_present & amp3_present & amp4_present:
                regions = 4

            # Assemble image
            if regions == 1:
                self.logger.debug("The code currently doesn't support single amplifier mode because this requires knowing which amplifer is used to get the proper orientation.")
                return
            if regions == 2:
                if chip == 'green':
                    image = np.flipud(np.concatenate((L0[CHIP + '_AMP1'].data, L0[CHIP + '_AMP2'].data), axis=1))
                if chip == 'red':
                    image = np.concatenate((L0[CHIP + '_AMP1'].data, L0[CHIP + '_AMP2'].data), axis=1)
            if regions == 4:
                image_bot = np.concatenate((L0[CHIP + '_AMP1'].data, L0[CHIP + '_AMP2'].data), axis=1)
                image_top = np.concatenate((L0[CHIP + '_AMP3'].data, L0[CHIP + '_AMP4'].data), axis=1)
                image = np.concatenate((image_bot, image_top), axis=0)

            # Determine if image needs to be divided by 2^16
            if np.nanmedian(image) > 400*2**16:
                twotosixteen = True
                image /= 2**16
            else:
                twotosixteen = False
        else:
            self.logger.debug('plot_L0_stitched_image: need to set chip="green" or "red"')
            return

        plt.figure(tight_layout=True)
        plt.figure(figsize=(10, 8), tight_layout=True)
        plt.imshow(image, cmap='viridis', origin='lower',
                   vmin=np.percentile(image,1),
                   vmax=np.percentile(image,99.5))
        if chip == 'green':
            plt.title('L0 (no processing) - Green CCD: ' + str(ObsID) + ' - ' + starname, fontsize=14)
        if chip == 'red':
            plt.title('L0 (no processing) - Red CCD: ' + str(ObsID) + ' - ' + starname, fontsize=14)
        plt.xlabel('Column (pixel number)', fontsize=14)
        plt.ylabel('Row (pixel number)', fontsize=14)
        cbar_label = 'ADU'
        if twotosixteen:
            cbar_label = cbar_label + r' / $2^{16}$'
        cbar = plt.colorbar(shrink=0.7, label=cbar_label)
        cbar.ax.yaxis.label.set_size(14)
        cbar.ax.tick_params(labelsize=12)
        plt.grid(False)

        # Display the plot
        if fig_path != None:
            plt.savefig(fig_path, dpi=1200, facecolor='w')
        if show_plot == True:
            plt.show()
        plt.close()
