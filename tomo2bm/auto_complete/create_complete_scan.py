import subprocess
from tomo2bm import log

def run(fname):
    try:
        # Form auto-complete for scan
        out = subprocess.Popen(['tomo', 'scan', '-h'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
        stdout, _ = out.communicate()
        stdout = str(stdout)

        cmdscan = []
        parscan = []
        st = stdout.find("optional")
        while(1):
            st = stdout.find('--', st)
            end = min(stdout.find(' ', st),stdout.find('\\n', st))
            if(st < 0):
                break            
            cmdscan.append(stdout[st:end])            
            st = stdout.find('(default:', end)                
            st1 = stdout.find('--', end)                
            if(st1>st or st1<0):
                end = stdout.find(')', st)
                parscan.append(stdout[st+9:end].replace(" ","").replace("\\n",""))                
            else:
                parscan.append("") 
            st = end        
        # Create bash file
        fid = open(fname, 'w')
        fid.write(
            '#/usr/bin/env bash\n _tomo()\n{\n\tlocal cur prev opts\n\tCOMPREPLY=()\n\tcur="${COMP_WORDS[COMP_CWORD]}"\n\tprev="${COMP_WORDS[COMP_CWORD-1]}"\n')

        # check all tomo scan
        fid.write('\tif [[ ${prev} == "scan" ]] ; then\n')
        fid.write('\t\topts="')
        fid.write(' '.join(cmdscan))
        fid.write('"\n')
        fid.write(
            '\t\tCOMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )\n\t\treturn 0\n\tfi\n')

        for k in range(len(cmdscan)):
            fid.write('\tif [[ ${prev} == "')
            fid.write(cmdscan[k])
            fid.write('" ]] ; then\n')
            fid.write('\t\topts="')
            fid.write(parscan[k])
            fid.write('"\n')
            fid.write(
                '\t\tCOMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )\n\t\treturn 0\n\tfi\n')
        fid.write('}\n')
        fid.write('complete -F _tomo tomo')
        fid.close()
    except:
        log.error('Autocomplete file was not created')