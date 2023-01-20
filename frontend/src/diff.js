/**
 * Adapted from https://github.com/kpdecker/jsdiff/blob/master/src/diff/base.js
 * (BSD License)
 */

export function diff(oldString, newString, options = {equals(a, b) { return a == b; }}) {
  let newLen = newString.length, oldLen = oldString.length;
  let editLength = 1;
  let maxEditLength = newLen + oldLen;
  if(options.maxEditLength) {
    maxEditLength = Math.min(maxEditLength, options.maxEditLength);
  }

  let bestPath = [{ newPos: -1, components: [] }];

  // Seed editLength = 0, i.e. the content starts with the same values
  let oldPos = extractCommon(options, bestPath[0], newString, oldString, 0);
  if (bestPath[0].newPos + 1 >= newLen && oldPos + 1 >= oldLen) {
    // Identity per the equality and tokenizer
    return [{value: newString, count: newString.length}];
  }

  for (editLength = 1; editLength <= maxEditLength; ++editLength) {
    for (let diagonalPath = -1 * editLength; diagonalPath <= editLength; diagonalPath += 2) {
      let basePath;
      let addPath = bestPath[diagonalPath - 1],
          removePath = bestPath[diagonalPath + 1],
          oldPos = (removePath ? removePath.newPos : 0) - diagonalPath;
      if (addPath) {
        // No one else is going to attempt to use this value, clear it
        bestPath[diagonalPath - 1] = undefined;
      }

      let canAdd = addPath && addPath.newPos + 1 < newLen,
          canRemove = removePath && 0 <= oldPos && oldPos < oldLen;
      if (!canAdd && !canRemove) {
        // If this path is a terminal then prune
        bestPath[diagonalPath] = undefined;
        continue;
      }

      // Select the diagonal that we want to branch from. We select the prior
      // path whose position in the new string is the farthest from the origin
      // and does not pass the bounds of the diff graph
      if (!canAdd || (canRemove && addPath.newPos < removePath.newPos)) {
        basePath = clonePath(removePath);
        pushComponent(basePath.components, undefined, true);
      } else {
        basePath = addPath; // No need to clone, we've pulled it from the list
        basePath.newPos++;
        pushComponent(basePath.components, true, undefined);
      }

      oldPos = extractCommon(options, basePath, newString, oldString, diagonalPath);

      // If we have hit the end of both strings, then we are done
      if (basePath.newPos + 1 >= newLen && oldPos + 1 >= oldLen) {
        return buildValues(options, basePath.components, newString, oldString);
      } else {
        // Otherwise track this path as a potential candidate and continue.
        bestPath[diagonalPath] = basePath;
      }
    }
  }
}

function extractCommon({equals}, basePath, newString, oldString, diagonalPath) {
  let newLen = newString.length,
      oldLen = oldString.length,
      newPos = basePath.newPos,
      oldPos = newPos - diagonalPath,

      commonCount = 0;
  while (newPos + 1 < newLen && oldPos + 1 < oldLen && equals(newString[newPos + 1], oldString[oldPos + 1])) {
    newPos++;
    oldPos++;
    commonCount++;
  }

  if (commonCount) {
    basePath.components.push({count: commonCount});
  }

  basePath.newPos = newPos;
  return oldPos;
}

function pushComponent(components, added, removed) {
  let last = components[components.length - 1];
  if (last && last.added === added && last.removed === removed) {
    // We need to clone here as the component clone operation is just
    // as shallow array clone
    components[components.length - 1] = {count: last.count + 1, added: added, removed: removed };
  } else {
    components.push({count: 1, added: added, removed: removed });
  }
}

function buildValues({equals, useLongestToken}, components, newString, oldString) {
  let componentPos = 0,
      componentLen = components.length,
      newPos = 0,
      oldPos = 0;

  for (; componentPos < componentLen; componentPos++) {
    let component = components[componentPos];
    if (!component.removed) {
      if (!component.added && useLongestToken) {
        let value = newString.slice(newPos, newPos + component.count);
        value = value.map(function(value, i) {
          let oldValue = oldString[oldPos + i];
          return oldValue.length > value.length ? oldValue : value;
        });

        component.value = value;
      } else {
        component.value = newString.slice(newPos, newPos + component.count);
      }
      newPos += component.count;

      // Common case
      if (!component.added) {
        oldPos += component.count;
      }
    } else {
      component.value = oldString.slice(oldPos, oldPos + component.count);
      oldPos += component.count;

      // Reverse add and remove so removes are output first to match common convention
      // The diffing algorithm is tied to add then remove output and this is the simplest
      // route to get the desired output with minimal overhead.
      if (componentPos && components[componentPos - 1].added) {
        let tmp = components[componentPos - 1];
        components[componentPos - 1] = components[componentPos];
        components[componentPos] = tmp;
      }
    }
  }

  // Special case handle for when one terminal is ignored (i.e. whitespace).
  // For this case we merge the terminal into the prior string and drop the change.
  // This is only available for string mode.
  let lastComponent = components[componentLen - 1];
  if (componentLen > 1
      && typeof lastComponent.value === 'string'
      && (lastComponent.added || lastComponent.removed)
      && equals('', lastComponent.value)) {
    components[componentLen - 2].value += lastComponent.value;
    components.pop();
  }

  return components;
}

function clonePath(path) {
  return { newPos: path.newPos, components: path.components.slice(0) };
}

export function diffSample(languages, previous, sample) {
  // Only mark different if neither of the columns is the same.
  const equals = (a, b) => !languages.every(lang => a[lang] != b[lang]);
  
  // Mark pairs that have exactly the same text on both sides as identical.
  const identical = (a, b) => languages.every(lang => a[lang] == b[lang]);

  const chunks = diff(previous?.stdout || [], sample?.stdout || [], {equals});

  let offset = 0;

  // Now also fish out all those rows that appear the same, but have
  // a difference in only one of the languages
  for (let i = 0; i < chunks.length; ++i) {
    console.assert(chunks[i].count === chunks[i].value.length);

    if (chunks[i].added)
      continue;

    if (chunks[i].removed) {
      offset += chunks[i].count;
      continue;
    }

    let first, last; // first offset of difference, offset of the first identical that follows.

    // Search for the first different sentence pair in this mutation block.
    for (first = 0; first < chunks[i].value.length; ++first) {
      if (!identical(previous.stdout[offset + first], chunks[i].value[first]))
        break;
    }

    // Did we find the first different sentence pair? If not skip this
    // chunk of chunks.
    if (first == chunks[i].value.length) {
      offset += chunks[i].count;
      continue;
    }

    // Find the first line that is identical again, the end of our
    // 'changed' block.
    for (last = first+1; last < chunks[i].value.length; ++last) {
      if (identical(previous.stdout[offset + last], chunks[i].value[last]))
        break;
    }

    console.assert(last <= chunks[i].value.length);

    // If it's not the first line of the mutation, we need to split it
    // in at least two (maybe three)
    if (first > 0) {
      chunks.splice(i, 0, {count: first, value: chunks[i].value.slice(0, first)})
      ++i; // We inserted it before the one we're handling right now,
           // so increase `i` accordingly
    }

    chunks[i].value = chunks[i].value.slice(first);
    chunks[i].count = last - first;
    chunks[i].changed = true;

    // If the mutation contains lines that are the same after the
    // changed ones, add those back in as well. Make sure they are
    // evaluated next.
    if (last - first < chunks[i].value.length) {
      const count = chunks[i].value.length - (last - first);
      chunks.splice(i+1, 0, {count, value: chunks[i].value.slice(last - first)});
      chunks[i].value = chunks[i].value.slice(0, last - first)
      // Do not increase i so next iteration looks at this newly added
      // one, there might be more changes here!
    }

    console.assert(chunks[i].value.every((curr, i) => !identical(previous.stdout[offset + first + i], curr)));

    // TODO clean this up this is a test.
    chunks[i].differences = chunks[i].value.map((current, i) => ({previous: previous.stdout[offset + first + i], current}));

    offset += last; // Add the offset for this plus optionally the
                    // spliced in identical chunk we added.
  }

  return readonly(chunks);
}
