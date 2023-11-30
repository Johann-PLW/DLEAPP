import json
import argparse
import io
import os.path
import typing
import plugin_loader
import scripts.report as report
import traceback

from scripts.search_files import *
from scripts.ilapfuncs import *
from scripts.version_info import dleapp_version
from time import process_time, gmtime, strftime

def validate_args(args):
    if args.artifact_paths or args.create_profile:
        return  # Skip further validation if --artifact_paths is used

    # Ensure other arguments are provided
    mandatory_args = ['input_path', 'output_path', 't']
    for arg in mandatory_args:
        value = getattr(args, arg)
        if value is None:
            raise argparse.ArgumentError(None, f'No {arg.upper()} provided. Run the program again.')

    # Check existence of paths
    if not os.path.exists(args.input_path):
        raise argparse.ArgumentError(None, 'INPUT file/folder does not exist! Run the program again.')

    if not os.path.exists(args.output_path):
        raise argparse.ArgumentError(None, 'OUTPUT folder does not exist! Run the program again.')

    if args.load_profile and not os.path.exists(args.load_profile):
        raise argparse.ArgumentError(None, 'DLEAPP Profile file not found! Run the program again.')
        

def create_profile(available_plugins, path):
    available_parsers = []
    for parser_data in available_plugins:
        available_parsers.append((parser_data.category, parser_data.name))
    
    available_parsers.sort()
    parsers_in_profile = {}
    
    user_choice = ''
    print('-' * 50)
    print('Welcome to the DLEAPP Profile file creation\n')
    instructions = 'You can type:\n'
    instructions += '   - \'a\' to add or remove parsers in the profile file\n'
    instructions += '   - \'l\' to display the list of all available parsers with their number\n'
    instructions += '   - \'p\' to display the parsers added into the profile file\n'
    instructions += '   - \'q\' to quit and save\n'
    while not user_choice:
        print(instructions)
        user_choice = input('Please enter your choice: ').lower()
        print()
        if user_choice == "l":
            print('Available parsers:')
            for number, available_plugin in enumerate(available_parsers):
                print(number + 1, available_plugin)
            print()
            user_choice = ''
        elif user_choice == "p":
            if parsers_in_profile:
                for number, parser in parsers_in_profile.items():
                    print(number, parser)
                print()
            else:
                print('No parser added to the profile file\n')
            user_choice = ''
        elif user_choice == 'a':
            parser_numbers = input('Enter the numbers of parsers, seperated by a comma, to add or remove in the profile file: ')
            parser_numbers = parser_numbers.split(',')
            parser_numbers = [parser_number.strip() for parser_number in parser_numbers]
            for parser_number in parser_numbers:
                if parser_number.isdigit():
                    parser_number = int(parser_number)
                    if parser_number > 0 and parser_number <= len(available_parsers):
                        if parser_number not in parsers_in_profile:
                            parser_to_add = available_parsers[parser_number - 1]
                            parsers_in_profile[parser_number] = parser_to_add
                            print(f'parser number {parser_number} {parser_to_add} was added')
                        else:
                            parser_to_remove = parsers_in_profile[parser_number]
                            print(f'parser number {parser_number} {parser_to_remove} was removed')
                            del parsers_in_profile[parser_number]
                    else:
                        print('Please enter the number of a parser!!!\n')
            print()
            user_choice = ''
        elif user_choice == "q":
            if parsers_in_profile:
                parsers = [parser_info[1] for parser_info in parsers_in_profile.values()]
                profile_filename = ''
                while not profile_filename:
                    profile_filename = input('Enter the name of the profile: ')
                profile_filename += '.dlprofile'
                filename = os.path.join(path, profile_filename)
                with open(filename, "wt", encoding="utf-8") as profile_file:
                    json.dump({"leapp": "dleapp", "format_version": 1, "plugins": parsers}, profile_file)
                print('\nProfile saved:', filename)
            else:
                print('No parser added. The profile file was not created.\n')
            return
        else:
            print('Please enter a valid choice!!!\n')
            user_choice = ''


def main():
    parser = argparse.ArgumentParser(description='DLEAPP: Drones Logs, Events, and Properties Parser.')
    parser.add_argument('-t', choices=['fs', 'tar', 'zip', 'gz'], required=False, type=str.lower, action="store",
                        help="Input type (fs = extracted to file system folder)")
    parser.add_argument('-o', '--output_path', required=False, action="store", help='Output folder path')
    parser.add_argument('-i', '--input_path', required=False, action="store", help='Path to input file/folder')
    parser.add_argument('-w', '--wrap_text', required=False, action="store_false", default=True,
                        help='Do not wrap text for output of data files')
    parser.add_argument('-l', '--load_profile', required=False, action="store", help="Path to DLEAPP Profile file (.dlprofile).")
    parser.add_argument('-c', '--create_profile', required=False, action="store",
                        help=("Generate a DLEAPP Profile file (.dlprofile) into the specified path. "
                              "This argument is meant to be used alone, without any other arguments."))
    parser.add_argument('-p', '--artifact_paths', required=False, action="store_true",
                        help=("Generate a text file list of artifact paths. "
                              "This argument is meant to be used alone, without any other arguments."))
        
    loader = plugin_loader.PluginLoader()
    available_plugins = list(loader.plugins)
    profile_filename = None
    
    print(f"Info: {len(available_plugins)} plugins loaded.")
    selected_plugins = available_plugins.copy()

    args = parser.parse_args()

    try:
        validate_args(args)
    except argparse.ArgumentError as e:
        parser.error(str(e))

    if args.artifact_paths:
        print('Artifact path list generation started.')
        print('')
        with open('path_list.txt', 'a') as paths:
            for plugin in loader.plugins:
                if isinstance(plugin.search, tuple):
                    for x in plugin.search:
                        paths.write(x+'\n')
                        print(x)
                else:  # TODO check that this is actually a string?
                    paths.write(plugin.search+'\n')
                    print(plugin.search)
        print('')
        print('Artifact path list generation completed')    
        return

    if args.create_profile:
        if os.path.isdir(args.create_profile):
            create_profile(selected_plugins, args.create_profile)
            return
        else:
            print('OUTPUT folder for storing DLEAPP Profile file does not exist!\nRun the program again.')
            return

    if args.load_profile:
        profile_filename = args.load_profile
        profile_load_error = None
        with open(profile_filename, "rt", encoding="utf-8") as profile_file:
            try:
                profile = json.load(profile_file)
            except json.JSONDecodeError as json_ex:
                profile_load_error = f"File was not a valid profile file: {json_ex}"
                print(profile_load_error)
                return

        if not profile_load_error:
            if isinstance(profile, dict):
                if profile.get("leapp") != "dleapp" or profile.get("format_version") != 1:
                    profile_load_error = "File was not a valid profile file: incorrect LEAPP or version"
                    print(profile_load_error)
                    return
                else:
                    profile_plugins = set(profile.get("plugins", []))
                    selected_plugins = [selected_plugin for selected_plugin in available_plugins 
                                        if selected_plugin.name in profile_plugins]
            else:
                profile_load_error = "File was not a valid profile file: invalid format"
                print(profile_load_error)
                return
    
    input_path = args.input_path
    extracttype = args.t
    wrap_text = args.wrap_text
    output_path = os.path.abspath(args.output_path)

    # File system extractions can contain paths > 260 char, which causes problems
    # This fixes the problem by prefixing \\?\ on each windows path.
    if is_platform_windows():
        if input_path[1] == ':' and extracttype =='fs': input_path = '\\\\?\\' + input_path.replace('/', '\\')
        if output_path[1] == ':': output_path = '\\\\?\\' + output_path.replace('/', '\\')

    out_params = OutputParameters(output_path)

    try:
        casedata
    except NameError:
        casedata = {}

        crunch_artifacts(selected_plugins, extracttype, input_path, out_params, 1, wrap_text, loader, casedata, profile_filename)

def crunch_artifacts(
        plugins: typing.Sequence[plugin_loader.PluginSpec], extracttype, input_path, out_params, ratio, wrap_text,
        loader: plugin_loader.PluginLoader, casedata, profile_filename):
    start = process_time()

    logfunc('Processing started. Please wait. This may take a few minutes...')

    logfunc('\n--------------------------------------------------------------------------------------')
    logfunc(f'DLEAPP v{dleapp_version}: Drones Logs, Events, and Properties Parser')
    logfunc('Objective: Triage Drone Extractions.')
    logfunc('By: Alexis Brignoni | @AlexisBrignoni | abrignoni.com')
    logfunc('By: Yogesh Khatri   | @SwiftForensics | swiftforensics.com\n')
    logdevinfo()

    seeker = None
    try:
        if extracttype == 'fs':
            seeker = FileSeekerDir(input_path)

        elif extracttype in ('tar', 'gz'):
            seeker = FileSeekerTar(input_path, out_params.temp_folder)

        elif extracttype == 'zip':
            seeker = FileSeekerZip(input_path, out_params.temp_folder)

        else:
            logfunc('Error on argument -o (input type)')
            return False
    except Exception as ex:
        logfunc('Had an exception in Seeker - see details below. Terminating Program!')
        temp_file = io.StringIO()
        traceback.print_exc(file=temp_file)
        logfunc(temp_file.getvalue())
        temp_file.close()
        return False

    # Now ready to run
    if profile_filename:
        logfunc(f'Loaded profile: {profile_filename}')
    logfunc(f'Artifact categories to parse: {len(plugins)}')
    logfunc(f'File/Directory selected: {input_path}')
    logfunc('\n--------------------------------------------------------------------------------------')

    log = open(os.path.join(out_params.report_folder_base, 'Script Logs', 'ProcessedFilesLog.html'), 'w+', encoding='utf8')
    nl = '\n' #literal in order to have new lines in fstrings that create text files
    log.write(f'Extraction/Path selected: {input_path}<br><br>')
    
    categories_searched = 0
    # Search for the files per the arguments
    for plugin in plugins:
        if isinstance(plugin.search, list) or isinstance(plugin.search, tuple):
            search_regexes = plugin.search
        else:
            search_regexes = [plugin.search]
        files_found = []
        log.write(f'<b>For {plugin.name} parser</b>')
        for artifact_search_regex in search_regexes:
            found = seeker.search(artifact_search_regex)
            if not found:
                log.write(f'<ul><li>No file found for regex <i>{artifact_search_regex}</i></li></ul>')
            else:
                log.write(f'<ul><li>{len(found)} {"files" if len(found) > 1 else "file"} for regex <i>{artifact_search_regex}</i> located at:')
                for pathh in found:
                    if pathh.startswith('\\\\?\\'):
                        pathh = pathh[4:]
                    log.write(f'<ul><li>{pathh}</li></ul>')
                log.write(f'</li></ul>')
                files_found.extend(found)
        if files_found:
            logfunc()
            logfunc('{} [{}] artifact started'.format(plugin.name, plugin.module_name))
            category_folder = os.path.join(out_params.report_folder_base, plugin.category)
            if not os.path.exists(category_folder):
                try:
                    os.mkdir(category_folder)
                except (FileExistsError, FileNotFoundError) as ex:
                    logfunc('Error creating {} report directory at path {}'.format(plugin.name, category_folder))
                    logfunc('Error was {}'.format(str(ex)))
                    continue  # cannot do work
            try:
                plugin.method(files_found, category_folder, seeker, wrap_text)
            except Exception as ex:
                logfunc('Reading {} artifact had errors!'.format(plugin.name))
                logfunc('Error was {}'.format(str(ex)))
                logfunc('Exception Traceback: {}'.format(traceback.format_exc()))
                continue  # nope

            logfunc('{} [{}] artifact completed'.format(plugin.name, plugin.module_name))

        categories_searched += 1
        GuiWindow.SetProgressBar(categories_searched * ratio)
    log.close()

    logfunc('')
    logfunc('Processes completed.')
    end = process_time()
    run_time_secs = end - start
    run_time_HMS = strftime('%H:%M:%S', gmtime(run_time_secs))
    logfunc("Processing time = {}".format(run_time_HMS))

    logfunc('')
    logfunc('Report generation started.')
    # remove the \\?\ prefix we added to input and output paths, so it does not reflect in report
    if is_platform_windows(): 
        if out_params.report_folder_base.startswith('\\\\?\\'):
            out_params.report_folder_base = out_params.report_folder_base[4:]
        if input_path.startswith('\\\\?\\'):
            input_path = input_path[4:]
    report.generate_report(out_params.report_folder_base, run_time_secs, run_time_HMS, extracttype, input_path, casedata)
    logfunc('Report generation Completed.')
    logfunc('')
    logfunc(f'Report location: {out_params.report_folder_base}')
    return True

if __name__ == '__main__':
    main()
