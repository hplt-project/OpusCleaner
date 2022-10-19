export function formatNumberSuffix(n) {
	let suffix = 'th';

	if (n % 10 === 1 && n % 100 !== 11)
		suffix = 'st';
	else if (n % 10 === 2 && n % 100 !== 12)
		suffix = 'nd';
	else if (n % 10 === 3 && n % 100 !== 13)
		suffix = 'rd';

	return `${n}${suffix}`;
}

export function formatSize(size) {
	const i = size == 0 ? 0 : Math.floor(Math.log(size) / Math.log(1024));
	return (size / Math.pow(1024, i)).toFixed(2) + ' ' + ['B', 'kB', 'MB', 'GB', 'TB'][i];
}
