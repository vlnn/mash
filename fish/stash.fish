function stash --description 'Store the previous command under the given words'
    mash add "$argv -> $history[1]"
end
