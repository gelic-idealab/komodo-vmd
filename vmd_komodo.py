# Project Komodo
# Dennis Piehl
# VMD Tkinter GUI for uploading structures to Komodo

import os
import subprocess
from tkinter import *
from tkinter import filedialog
import time
import datetime as dt
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
    Python script for running VMD GUI executable (from within script), allow user to open up PDB file 
    and adjust the representation of the structure to however they wish it to look, then parse/copy 
    the Logfile output in order to determine the settings to use to render the molecule and subsequently 
    upload the model file(s).


    TODO:
        - Replace hard-coded 'creatorID' of '1' in second Komodo request with auto-determined value (OR, simply send the same API token to Komodo as done in the first request)
        - Send along file-generated metadata for each upload to Komodo?
            - Currently, if I try to send the metadata as a json.dumps(metdata) within the "description" field of the post, the request seems to get stalled up. Maybe the value is too many characters long?
            - Or, can just allow user to specify a description of each file before exporting
        - Make post requests to Komodo VERIFY the SSL certificates
            - Currently, 'verify' is set to False, because if it's set to True the request fails with:
                >>> (Caused by SSLError(SSLError("bad handshake: Error([('SSL routines', 'tls_process_server_certificate', 'certificate verify failed')])")
            - Also, although setting it to False allows the request to succeed, it still generates a warning of 'InsecureRequestWarning'. Because of this, I'm currently suppressing this warning at the import block above. So, once this issue is fixed, those two 'urlib3' lines in that block can be removed.
        - Move commands from main() to KomodoGUI class for 'Export' and 'Upload' (where they belong...)
        - Add a Tkinter pop-up 'Welcome' window before VMD opens, to tell the user what to do
            I.e., Open and modify the molecule to however you like, then click 'Export' for each new vis state you want to export and upload, then when all finished click 'File'->'Quit', and follow all instructions for upload to Komodo)
        - Add "help" note on Tk window for "Where to obtain API token"
"""

def main():
    """
    Main function for VMD to Komodo export and upload.
    
    User must specify location/path to their local VMD executable. 
    See examples below for location in Windows & Linux system.

    """
    global mol_export_count
    global time_now
    global export_file_list
    global vmd_installation

    ## Specify location of local VMD executable
    vmd_installation = r'C:\Program Files (x86)\University of Illinois\VMD\vmd.exe'    # Windows installation
    # vmd_installation = '/usr/local/bin/vmd'    # Ubuntu installation

    ## Initialize global variables
    mol_export_count = 0
    export_file_list = []
    time_now = dt.datetime.now().strftime('%y%m%d-%H%M%S')

    ## Create a 'startup.tcl' script to run for opening up main VMD windows for user and initiating TCL command output to file 'command_log.tcl' (instead of having to parse the standard output)
    try:
        default_rep = 'mol default color {Name}\nmol default style {Licorice 0.100000 12.000000 12.000000}\n'
        if 'startup.tcl' not in os.listdir('.'):
            startup_commands = 'menu main on\nlogfile command_log.tcl\n'+default_rep
            with open('./startup.tcl', 'w') as o:
                o.write(startup_commands+'\n')

        ## This is necessary because need to declare defaults when running rendering script below, not just for user prep
        if 'startup_rep.tcl' not in os.listdir('.'):
            with open('startup_rep.tcl', 'w') as o:
                o.write(default_rep)

    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))
        return

                
    ## Start-up VMD (using startup.tcl script)
    try:
        vmd_proc = subprocess.Popen([vmd_installation, '-startup', './startup.tcl'])
    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))
        print("\nPlease double-check the path to your VMD installation, as specified in the vmd_komodo.py script!")
        return

    ## Initiate Tkinter window
    try:
        root = Tk()
        komodo_gui = KomodoGUI(root)
        root.mainloop()
    
    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))

    ## Kill VMD subprocess
    try:
        vmd_proc.kill()
        time.sleep(2) # Give VMD enough time to fully terminate before trying to rename 'command_log.tcl' file

    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))

    ## Remove or Rename generated TCL files
    try:
        os.rename('command_log.tcl', 'command_log_'+time_now+'.tcl')
        os.rename('render.tcl', 'render_'+time_now+'.tcl')
    except Exception as emsg:
        # print("EXCEPTION: "+str(emsg))
        pass

    return


def read_and_append_log_commands_to_render_script(log_in, specified_filename):
    """
    Read and append the render command to the render.tcl file.
    
    :param log_in: Active log file being generated by VMD in the current working directory. 
                   Corresponds to 'command_log.tcl' file as used in the script here. 
    
    :param specified_filename: User-entered filename to use as the name for the exported/rendered file.
    
    """
    global mol_export_count
    global time_now
    global export_file_list

    try:
        if 'render.tcl' in os.listdir('.'):
            with open('render.tcl', 'r') as r:
                num_lines_in_render = len(r.read().splitlines())
        else:
            num_lines_in_render = 0

        num_lines_to_skip_in_log = num_lines_in_render - mol_export_count

        with open(log_in, 'r') as r:
            log_commands = r.readlines()[num_lines_to_skip_in_log:]

        with open('render.tcl','a') as o:
            for log_cmd in log_commands:
                o.write(log_cmd)
            if not specified_filename.isspace() and len(specified_filename) > 0:
                output_filename = specified_filename+'.obj'
            else:
                output_filename = 'mol_out_'+str(mol_export_count)+'_'+time_now+'.obj'
            o.write('render Wavefront ./'+output_filename+'\n')
            mol_export_count += 1
            export_file_list.append(output_filename)
            print("Mol filename (.obj & .mtl):", output_filename)
            if output_filename.endswith('.obj'): # Also add the '.mtl' file
                export_file_list.append(output_filename[:-4]+'.mtl')

    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))

    return


## KOMODO TKINTER WINDOW ##
## Tkinter GUI help obtained: https://python-textbok.readthedocs.io/en/1.0/Introduction_to_GUI_Programming.html
class KomodoGUI:
    def __init__(self, master):
        self.master = master
        master.title("Komodo Upload")
        self.upload_file_list = []

        self.label = Label(master, text="Prepare Molecule Views\nfor Export and Upload")
        self.label.grid(row=0, column=1, pady=3)

        self.L2 = Label(master, text="Specify filename (no spaces):")
        self.L2.grid(row=1, column=0, sticky=E, pady=2)
        self.E2 = Entry(master, bd=5)
        self.E2.grid(row=1, column=1, pady=2)

        self.add_to_export_button = Button(master, text="Add current mol view to export list", command=self.add_to_export_list)
        self.add_to_export_button.grid(row=1, column=2, sticky=W, pady=2)

        self.export_button = Button(master, text="Export mol list to OBJ/MTL files", command=self.export_mols)
        self.export_button.grid(row=2, column=1, pady=2)

        self.select_file_button = Button(master, text="Select existing file(s) to upload...", command=self.open_file_dialog)
        self.select_file_button.grid(row=3, column=1, pady=2)

        self.label2 = Label(master, text="Upload Files to Komodo")
        self.label2.grid(row=4, column=1, pady=8)

        self.L1 = Label(master, text="API Token:")
        self.L1.grid(row=5, column=0, sticky=E, pady=5)
        self.E1 = Entry(master, bd=5)
        self.E1.grid(row=5, column=1, pady=5)
        
        self.public_bool = IntVar()
        self.public_check = Checkbutton(master, text="Make upload Public?", variable=self.public_bool)
        self.public_check.grid(row=5, column=2, sticky=W, pady=5)
        
        self.upload_button = Button(master, text="Upload to Komodo", command=self.upload)
        self.upload_button.grid(row=6, column=1, pady=2)

        self.close_button = Button(master, text="Close", command=master.quit)
        self.close_button.grid(row=7, column=1, pady=8)

        
    def add_to_export_list(self):
        """
        Add current view of molecule to export list. 
        
        Calls separate function to do this, "read_and_append_log_commands_to_render_script()"
        """
        print("Adding current molecule view to export script.")
        
        try:
            entered_filename = str(self.E2.get())
            read_and_append_log_commands_to_render_script('command_log.tcl', entered_filename)
            
        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
        
        return

        
    def export_mols(self):
        """
        Now prepare and run render scripts in VMD text-mode to export molecules as OBJ/MTL files.
        
        Output files should be saved to the current worrking directory.
        """
        global vmd_installation
        global export_file_list
        
        try:
            if len(export_file_list) == 0:
                print("No molecules added to export list yet! (Nothing to export.)")
                return
        
            else:
                ## Add 'exit' to export/render script, so the text-mode VMD quits when done.
                ## NOTE THAT THIS MEANS ONCE YOU CLICK 'EXPORT'--YOU CAN NO LONGER ADD ANY NEW MOLS TO THE LIST!
                with open('render.tcl','a') as o:
                    o.write('\nexit\n')                
                print("Exporting molecule views to OBJ/MTL files!")
                render_out = subprocess.run([vmd_installation, '-dispdev', 'text', '-startup', 'startup_rep.tcl', '-e', 'render.tcl'], stdout=subprocess.PIPE)
                print("Done!")

        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            return
        
        return
        
            
    def open_file_dialog(self):
        """
        Open file browser window for user to select additional, previously exported, 
        OBJ files to the list of file to upload ("upload_file_list").
        
        """
        
        try:
            selected_filename =  filedialog.askopenfilename(initialdir = ".", title = "Select file", filetypes = (("obj files","*.obj"), ("mtl files","*.mtl"), ("all files","*.*")))
            
            if os.path.exists(selected_filename):
                self.upload_file_list.append(selected_filename)
                print("File added to upload list:", selected_filename)
                
                ## Also add the '.mtl' file if not already added
                if selected_filename.endswith('.obj'): 
                    selected_filename_mtl = selected_filename[:-4]+'.mtl'
                    if selected_filename_mtl not in self.upload_file_list:
                        if os.path.exists(selected_filename_mtl):
                            self.upload_file_list.append(selected_filename_mtl)
                            print("File added to upload list:", selected_filename_mtl)
            else:
                print("No existing file selected.")
                pass
            
        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            return None
        
        return

            
    def upload(self):
        """
        Start the upload process. Checks for the API tokoen, Public/Private selection, 
        and if any molecules have been added to the upload list.
        
        Calls separate function to perform the actual upload, "upload_files_to_komodo()"
        """
        global export_file_list
        
        try:
            entered_api_token = self.E1.get()
            make_public = bool(self.public_bool.get())
        
            for f in export_file_list:
                if f not in self.upload_file_list:
                    self.upload_file_list.append(f)

        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            return
        
        try:
            if len(self.upload_file_list) == 0:
                print("No molecules exported or added to upload list yet (nothing to upload).")
                return
            
            else:
                print("Will try to upload the following files:")
                for f in self.upload_file_list:
                    print("  ", f)
                    
                if make_public:
                    print("Files will be uploaded a PUBLICLY available assets.")
                else:
                    print("Files will be uploaded a PRIVATE assets.")

                upload_files_to_komodo(self.upload_file_list, entered_api_token, make_public)

        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            return
        
        return



def upload_files_to_komodo(file_list, api_token, public_upload_bool):
    """
    Function to loop over each file to upload and send it to the AWS S3 bucket that Komodo accesses as 
    a 'multipart/form-data' POST request.
    
    Requests ref.: https://requests.readthedocs.io/en/master/user/quickstart/#post-a-multipart-encoded-file

    Order of API request events:
        1) Send POST request to Komodo server -> returns a presigned post for S3
        2) Send POST with file to AWS S3 bucket using presigned post
        3) Send POST to Komodo server with file information of S3 upload (if successful)
    
    Also, gather file metadata using a separate function, "get_general_file_metadata();"
    however, cannot currently send metadata in "Description" field of third API call--
    program stalls when posting the request.

    Portion of this code was obtained from a script by Rob Wallace as part of the project, '3deposit' (script name: aws-service.py).

    :param file_list: List of filenames to upload. (Corresponds to 'self.upload_file_list' parameter used above.)
    :param api_token: User-specified Komodo API token. Can be obtained from API web frontend. 
                      Must be entered into the tkinter text entry field.
    :param public_upload_bool: Boolean value indicating if the list of files should be uploaded as public assets or not.
    """

    # api_token = "test" # For testing purposes only!!!
    
    ## Check if user-entered API token is at least more than 4 characters (will certainly be longer than this, but here just check if they typed in anything)
    ## Later--will want to actually check ifthe API token exists in the Komodo database.
    if len(api_token) < 4:
        print("Please Enter a Valid API Token.")
        return
    else:
        pass

    for fil in file_list:
        f = os.path.relpath(fil)
    
        if os.path.exists(f):   # Check to make sure the files exist
            print("\nBeginning upload for file:", f)
        else:
            print("Problem finding file,", f)
            print("Continuing onto next file...")
            continue

        file_metadata = {} # Initialize as empty dict, to avoid sending previous file metadata over as next file's
        
        try:
            ## Get gneral file metadata to send as "Description" field to Komodo
            ## Note: Not currently sent, since API call stalls when trying to send it.
            ## However, can still use this to grab just the filename (instead of the path)
            file_metadata = get_general_file_metadata(f)
            fname = file_metadata['filename']

            ## Send POST request to Komodo server to obtain a presigned S3 POST body
            r = requests.post('https://api.komodo-dev.library.illinois.edu/api/public/upload', headers={"X-API-KEY": api_token}, verify=False)  # For now, ignore verifying the SSL certificate (Change this later?)

            data = r.json()

            if r.status_code == 200:
                print("Obtain presigned AWS S3 POST body from Komodo:  Success.")
                pass
            elif 200 <= r.status_code < 300:
                print("Unexpected response code from initial Komodo POST request", f, ":", r.status_code)
                print("Double-check if file was uploaded to Komodo or not.")
                pass
            else:
                print("Problem uploading file:", f)
                print("Bad response code from Komodo request:", r.status_code)
                continue


            ## PARSE RESPONSE FROM SERVER TO PREPARE REQUEST FOR AWS
            aws_url = data['url']
            aws_fields = data['fields']
            aws_key = data['fields']['key']
            uuid = aws_key.split('/')[1]
            asset_path = ('/').join([aws_url, aws_key])
            asset_path = asset_path.replace(r'${filename}',fname)

            ## NOW SEND POST REQUEST TO AWS BUCKET
            post_file = {"file": open(f, 'rb')}
            r2 = requests.post(aws_url, data=aws_fields, files=post_file)
            
            if r2.status_code == 204:
                print("Send file to AWS S3 bucket for storage:  Success.")
                pass
            elif 200 <= r2.status_code < 300:
                print("Unexpected response code from AWS upload of file", f, ":", r2.status_code)
                print("Double-check that uploaded file looks OK on Komodo.")
                pass
            else:
                print("Problem uploading file:", f)
                print("Bad response code from AWS upload:", r2.status_code)
                continue
            
            ## Send POST to Komodo server with file information of S3 upload
            r3 = requests.post('https://api.komodo-dev.library.illinois.edu/api/portal/assets', data=json.dumps({"uuid": uuid, "assetName": fname, "description": "", "creatorId":1, "isPublic":public_upload_bool, "path": asset_path}), headers={'Content-Type':"application/json"}, verify=False)
            data3 = r3.json()

            if r3.status_code == 200:
                print("Finalize file upload for accesss on Komodo:  Success.")
                pass
            elif 200 <= r2.status_code < 300:
                print("Unexpected response code from Komodo post of file information", f, ":", r3.status_code)
                print("Double-check that uploaded file looks OK on Komodo.")
                pass
            else:
                print("Problem uploading file information to Komodo:", f)
                print("Bad response code from Komodo post of file information:", r3.status_code)
                continue
                
            print("Done uploading file:", f)


        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            return None
    
    print("All done uploading files!\n")

    return



def get_general_file_metadata(in_file):
    """
    # Function from metadata-service of 3deposit project #

    Extract the general file metadata/properties from a file (e.g., size, date modified, etc.).

    :param in_file: Path and filename of the file from which to extract generic metadata.
    :return file_info_dict: Dictionary of file metadata for the given file; otherwise, return None.
    """

    try:
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(in_file)

        file_info_dict = {
            "size" : size,  # in bytes
            "atime" : time.ctime(atime),    # time of last access
            "mtime" : time.ctime(mtime),    # time of last modified
            "ctime" : time.ctime(ctime),    # The “ctime” as reported by the operating system. On some systems (like Unix) is the time of the last metadata change, and, on others (like Windows), is the creation time (see platform documentation for details).
            }

        try:
            file_info_dict.update({"file_tree_path":in_file})

            if in_file.endswith('/'): # means it's a directory
                dirname = in_file.split('/')[-2]
                file_info_dict.update({"directory_name":dirname})
                file_info_dict.update({"ext":None})

            else:
                filename = in_file.split('/')[-1]    # in case the full path is given, get just the file of interest name
                file_info_dict.update({"filename":filename})
                file_ext = filename.split('.')[-1] # use this to "assume" filetype (of course, this is less than ideal)
                if file_ext != '':
                    file_info_dict.update({"ext":file_ext})
                else:
                    file_info_dict.update({"ext":None})

        except Exception as emsg:
            print("EXCEPTION: "+str(emsg))
            file_info_dict.update({"file_tree_path":None})
            file_info_dict.update({"filename":None})
            file_info_dict.update({"ext":None})

        return file_info_dict

    except Exception as emsg:
        print("EXCEPTION: "+str(emsg))
        return None


if __name__ == '__main__':
	main()
