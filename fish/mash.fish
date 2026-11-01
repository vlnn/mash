function mash --description 'Fuzzy search over ~/.mash records'
    set -l here (dirname (readlink -f (status filename)))
    command python3 -S $here/../run.py $argv
end
