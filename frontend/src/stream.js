// Async generator for lines
// From https://developer.mozilla.org/en-US/docs/Web/API/ReadableStreamDefaultReader/read#example_2_-_handling_text_line_by_line
export async function* lineIterator(reader) {
	const decoder = new TextDecoder("utf-8");
	let {value, done} = await reader.read();
	value = value ? decoder.decode(value, {stream: true}) : "";

	const re = /\r\n|\n|\r/gm;
	let startIndex = 0;

	while (true) {
		let result = re.exec(value);
		if (result) {
			yield value.substring(startIndex, result.index);
			startIndex = re.lastIndex;
			continue;
		}
		
		if (done)
			break;

		let remainder = value.substr(startIndex);
		({value, done} = await reader.read());
		value = remainder + (value ? decoder.decode(value, {stream: true}) : "");
		startIndex = 0;
		re.lastIndex = 0;
	}
	
	// if the last line didn't end in a newline char
	if (startIndex < value.length)
		yield value.substr(startIndex);
}

export async function* stream(url, options) {
	const response = await fetch(url, options);
	if (!response.ok)
		throw new Error(await response.text());
	const reader = response.body.getReader();
	for await (let line of lineIterator(reader)) {
		yield JSON.parse(line);
	}
}
