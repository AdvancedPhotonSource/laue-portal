import database.db_schema as db_schema
import config
import yaml
import sqlalchemy

engine = sqlalchemy.create_engine(f'sqlite:///{config.db_file}') 

def _clean(line):
    c = '#'
    if c in line: line = line[:line.index('#')-1]
    else: line = line.rstrip('\n').rstrip()
    return line

def read_config(path, conn):
    entries = {}; header_chain = []
    
    with open(path, 'r') as f:
        lines = list(map(_clean, f.readlines()))
    
    for line in lines:
        if line:
            
            n_spaces = next((i for i, c in enumerate(line) if c != ' '))
            n_tabs = int(n_spaces/4)
            
            header_chain = header_chain[:n_tabs]
            
            local_header, value = line.split(CLASSIFY_CHAR) # *[p.lstrip() for p in line.split(':')]
            local_header = local_header.lstrip() #*
            header_chain.append(local_header)
            
            #print(local_header, value)
            if value:
                value = value.lstrip() #*
                full_header = SPLIT_CHAR.join(header_chain)
                eval_value = eval(value)
                if isinstance(eval_value, (list, tuple)): # info on whether tuple or list not preserved
                    for i,v in enumerate(eval_value):
                        entries[f'{full_header}_{i}'] = v,SQLITE_TYPE_DICT[v.__class__.__name__]
                else:
                    entries[full_header] = eval_value,SQLITE_TYPE_DICT[eval_value.__class__.__name__]
    
    config_fields = []
    config_classes = []
    config_values = []
    for f,(v,c) in entries.items():
        print(f,(v,c))
        config_fields.append(f'{f}')
        config_classes.append(f'{c}')
        config_values.append(f'{v}')
        
    return config_fields,config_classes,config_values